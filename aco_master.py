import time
import math
import argparse
import threading
from concurrent import futures
import grpc
import aco_distributed_pb2
import aco_distributed_pb2_grpc


class ACOMaster(aco_distributed_pb2_grpc.ACOMasterServiceServicer):
    
    def __init__(self, graph_matrix, total_iterations=20, num_ants=10, alpha=1.0, beta=3.0, rho=0.5, q=10):
        self.distance_matrix = graph_matrix
        self.n = len(graph_matrix)
        self.total_iterations = total_iterations
        self.num_ants_per_worker = num_ants
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.q = q
        
        self.pheromone = [[1.0 for _ in range(self.n)] for _ in range(self.n)]
        
        self.current_iteration = 0
        self.finished = False
        self.best_cost = math.inf
        self.best_path = None
        
        self.solutions_current_iteration = []
        self.workers_completed = set()
        
        # Atributos para 2PC
        self.transaction_id = 0
        self.worker_addresses = {}
        self.worker_stubs = {}
        
        self.lock = threading.Lock()
        
        print(f"\n{'='*70}")
        print(f"  MESTRE ACO INICIADO COM 2PC")
        print(f"  Tamanho do grafo: {self.n} nós")
        print(f"  Iterações totais: {self.total_iterations}")
        print(f"  Formigas por worker: {self.num_ants_per_worker}")
        print(f"  Alpha: {self.alpha} | Beta: {self.beta} | Rho: {self.rho} | Q: {self.q}")
        print(f"{'='*70}\n")
    
    def register_worker(self, worker_id, address):
        """Registra um worker e cria stub para comunicacao 2PC"""
        if worker_id not in self.worker_addresses:
            self.worker_addresses[worker_id] = address
            channel = grpc.insecure_channel(address)
            self.worker_stubs[worker_id] = aco_distributed_pb2_grpc.TwoPhaseCommitServiceStub(channel)
            print(f"[Mestre] Worker {worker_id} registrado em {address}")
    
    def RequestWork(self, request, context):
        with self.lock:
            worker_id = request.worker_id
            
            # Registra worker se ainda nao foi registrado
            peer = context.peer()
            if worker_id not in self.worker_addresses:
                # Extrai endereco do peer
                # Formato IPv4: "ipv4:127.0.0.1:porta"
                # Formato IPv6: "ipv6:[::1]:porta"
                worker_port = 50051 + worker_id
                
                if 'ipv6' in peer:
                    # Para IPv6, usa localhost
                    worker_addr = f"localhost:{worker_port}"
                elif 'ipv4' in peer:
                    # Para IPv4, extrai IP
                    addr_parts = peer.split(':')
                    if len(addr_parts) >= 3:
                        ip = addr_parts[1]
                        worker_addr = f"{ip}:{worker_port}"
                    else:
                        worker_addr = f"localhost:{worker_port}"
                else:
                    # Fallback
                    worker_addr = f"localhost:{worker_port}"
                
                self.register_worker(worker_id, worker_addr)
            
            print(f"[Mestre] Worker {worker_id} solicitou trabalho (Iteração {self.current_iteration + 1}/{self.total_iterations})")
            
            if self.finished:
                return aco_distributed_pb2.WorkAssignment(
                    finished=True,
                    num_ants=0,
                    iteration=self.current_iteration
                )
            
            pheromone_flat = [val for row in self.pheromone for val in row]
            distance_flat = [val for row in self.distance_matrix for val in row]
            
            return aco_distributed_pb2.WorkAssignment(
                num_ants=self.num_ants_per_worker,
                iteration=self.current_iteration,
                pheromone_matrix=pheromone_flat,
                matrix_size=self.n,
                distance_matrix=distance_flat,
                finished=False,
                alpha=self.alpha,
                beta=self.beta
            )
    
    def SubmitSolution(self, request, context):
        with self.lock:
            worker_id = request.worker_id
            path = list(request.path)
            cost = request.cost
            iteration = request.iteration
            
            print(f"[Mestre] Worker {worker_id} enviou solução | Iteração: {iteration} | Custo: {cost:.2f}")
            
            self.solutions_current_iteration.append((path, cost))
            self.workers_completed.add(worker_id)
            
            if cost < self.best_cost:
                self.best_cost = cost
                self.best_path = path
                print(f"[Mestre] *** NOVA MELHOR SOLUÇÃO *** | Custo: {cost:.2f} | Caminho: {path}")
            
            response = aco_distributed_pb2.SolutionResponse(
                accepted=True,
                current_best_cost=self.best_cost,
                current_best_path=self.best_path if self.best_path else [],
                message=f"Solução recebida do Worker {worker_id}"
            )
            
            return response
    
    def _update_pheromones(self):
        """Atualiza feromônios com soluções coletadas"""
        for i in range(self.n):
            for j in range(self.n):
                self.pheromone[i][j] *= (1 - self.rho)
        
        for path, cost in self.solutions_current_iteration:
            deposit = self.q / cost
            for idx in range(len(path)):
                i = path[idx]
                j = path[(idx + 1) % len(path)]
                self.pheromone[i][j] += deposit
                self.pheromone[j][i] += deposit
    
    def _execute_two_phase_commit(self):
        """
        Executa protocolo Two-Phase Commit (2PC)
        Retorna True se commit foi bem sucedido, False se abortou
        """
        self.transaction_id += 1
        current_tx = self.transaction_id
        
        print(f"\n[2PC] ========== TRANSACAO {current_tx} ==========")
        
        # FASE 1: PREPARE (Voting Phase)
        print(f"[2PC] FASE 1: Enviando PREPARE para {len(self.worker_stubs)} worker(s)...")
        
        votes = {}
        for worker_id, stub in self.worker_stubs.items():
            try:
                request = aco_distributed_pb2.PrepareRequest(
                    transaction_id=current_tx,
                    iteration=self.current_iteration,
                    timestamp=int(time.time() * 1000)
                )
                
                response = stub.Prepare(request, timeout=5.0)
                votes[worker_id] = response.vote_yes
                
                vote_str = "VOTE_YES" if response.vote_yes else "VOTE_NO"
                print(f"[2PC] Worker {worker_id}: {vote_str} ({response.message})")
                
            except grpc.RpcError as e:
                print(f"[2PC] Worker {worker_id}: FALHA/TIMEOUT ({e.code()})")
                votes[worker_id] = False
        
        # Decisao: COMMIT apenas se TODOS votaram YES
        all_yes = all(votes.values()) and len(votes) == len(self.worker_stubs)
        
        # FASE 2: COMMIT ou ABORT
        if all_yes:
            print(f"[2PC] DECISAO: COMMIT (todos votaram YES)")
            print(f"[2PC] FASE 2: Atualizando feromônios...")
            
            # Atualiza feromônios localmente
            self._update_pheromones()
            print(f"[2PC] Feromônios atualizados com {len(self.solutions_current_iteration)} solucoes")
            
            # Envia COMMIT com feromônios atualizados para todos workers
            print(f"[2PC] FASE 2: Enviando COMMIT para worker(s)...")
            pheromone_flat = [val for row in self.pheromone for val in row]
            
            commit_acks = 0
            for worker_id, stub in self.worker_stubs.items():
                try:
                    request = aco_distributed_pb2.CommitRequest(
                        transaction_id=current_tx,
                        iteration=self.current_iteration,
                        updated_pheromone_matrix=pheromone_flat,
                        matrix_size=self.n
                    )
                    
                    response = stub.Commit(request, timeout=5.0)
                    if response.acknowledged:
                        commit_acks += 1
                        print(f"[2PC] Worker {worker_id}: ACK recebido")
                    
                except grpc.RpcError as e:
                    print(f"[2PC] Worker {worker_id}: Falha no ACK ({e.code()})")
            
            print(f"[2PC] COMMIT concluído ({commit_acks}/{len(self.worker_stubs)} ACKs)")
            return True
            
        else:
            print(f"[2PC] DECISAO: ABORT (nem todos votaram YES)")
            print(f"[2PC] FASE 2: Enviando ABORT para worker(s)...")
            
            # Envia ABORT para todos workers
            for worker_id, stub in self.worker_stubs.items():
                try:
                    request = aco_distributed_pb2.AbortRequest(
                        transaction_id=current_tx,
                        iteration=self.current_iteration,
                        reason="Um ou mais workers nao estavam prontos"
                    )
                    
                    response = stub.Abort(request, timeout=5.0)
                    if response.acknowledged:
                        print(f"[2PC] Worker {worker_id}: ABORT reconhecido")
                    
                except grpc.RpcError as e:
                    print(f"[2PC] Worker {worker_id}: Falha no ABORT ({e.code()})")
            
            print(f"[2PC] ABORT concluído (feromônios NAO atualizados)")
            return False
    
    def run_coordination(self, expected_workers=2):
        print(f"[Mestre] Aguardando {expected_workers} worker(s) para começar...\n")
        
        while self.current_iteration < self.total_iterations:
            iteration_start = time.time()
            
            print(f"\n{'='*70}")
            print(f"  ITERACAO {self.current_iteration + 1}/{self.total_iterations}")
            print(f"  Melhor custo global: {self.best_cost if self.best_cost != math.inf else 'N/A'}")
            print(f"{'='*70}\n")
            
            # Aguarda workers enviarem soluções
            self._wait_for_workers(expected_workers)
            
            # Executa protocolo 2PC para commit da iteração
            commit_success = False
            max_retries = 3
            retry_count = 0
            
            while not commit_success and retry_count < max_retries:
                if retry_count > 0:
                    print(f"\n[Mestre] Tentativa {retry_count + 1}/{max_retries} de commit...")
                
                with self.lock:
                    commit_success = self._execute_two_phase_commit()
                
                if not commit_success:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"[Mestre] Aguardando 2s antes de tentar novamente...")
                        time.sleep(2)
            
            if commit_success:
                print(f"\n[Mestre] Iteracao {self.current_iteration + 1} COMMITADA com sucesso")
                
                with self.lock:
                    self.solutions_current_iteration.clear()
                    self.workers_completed.clear()
                    self.current_iteration += 1
            else:
                print(f"\n[Mestre] ERRO: Iteracao {self.current_iteration + 1} ABORTADA apos {max_retries} tentativas")
                print(f"[Mestre] Pulando para proxima iteracao...")
                
                with self.lock:
                    self.solutions_current_iteration.clear()
                    self.workers_completed.clear()
                    self.current_iteration += 1
            
            iteration_time = time.time() - iteration_start
            print(f"\n[Mestre] Tempo total da iteracao: {iteration_time:.2f}s\n")
        
        with self.lock:
            self.finished = True
        
        print(f"\n{'='*70}")
        print(f"  ALGORITMO FINALIZADO!")
        print(f"  Melhor custo: {self.best_cost:.2f}")
        print(f"  Melhor caminho: {self.best_path}")
        print(f"{'='*70}\n")
    
    def _wait_for_workers(self, expected_workers, timeout=60):
        start_time = time.time()
        
        while True:
            with self.lock:
                if len(self.workers_completed) >= expected_workers:
                    print(f"[Mestre] Todos os {expected_workers} workers completaram suas tarefas!")
                    break
            
            if time.time() - start_time > timeout:
                with self.lock:
                    completed = len(self.workers_completed)
                print(f"[Mestre] TIMEOUT! Apenas {completed}/{expected_workers} workers responderam")
                break
            
            time.sleep(0.5)


def start_server(port, graph_matrix, iterations, ants, workers):
    master = ACOMaster(
        graph_matrix=graph_matrix,
        total_iterations=iterations,
        num_ants=ants
    )
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    aco_distributed_pb2_grpc.add_ACOMasterServiceServicer_to_server(master, server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    
    print(f"[Mestre] Servidor gRPC iniciado na porta {port}\n")
    
    coordination_thread = threading.Thread(
        target=master.run_coordination,
        args=(workers,),
        daemon=True
    )
    coordination_thread.start()
    
    try:
        coordination_thread.join()
        print("\n[Mestre] Algoritmo concluído! Aguardando 5s antes de finalizar servidor...")
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n\n[Mestre] Interrompido pelo usuário...")
    finally:
        server.stop(grace=5)
        print("[Mestre] Servidor finalizado com sucesso.")


def main():
    parser = argparse.ArgumentParser(description='Mestre ACO Distribuído')
    parser.add_argument('--port', type=int, default=50051, help='Porta do servidor (padrão: 50051)')
    parser.add_argument('--iterations', type=int, default=10, help='Número de iterações (padrão: 10)')
    parser.add_argument('--ants', type=int, default=5, help='Formigas por worker (padrão: 5)')
    parser.add_argument('--workers', type=int, default=2, help='Número esperado de workers (padrão: 2)')
    
    args = parser.parse_args()
    
    graph = [
        [0, 2, 2, 5, 7],
        [2, 0, 4, 8, 2],
        [2, 4, 0, 1, 3],
        [5, 8, 1, 0, 2],
        [7, 2, 3, 2, 0],
    ]
    
    start_server(args.port, graph, args.iterations, args.ants, args.workers)


if __name__ == '__main__':
    main()