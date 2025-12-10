import time
import random
import argparse
import threading
from concurrent import futures
import grpc
import aco_distributed_pb2
import aco_distributed_pb2_grpc


class LamportClock:
    """
    Implementação manual de Relógio de Lamport para ordenação de eventos distribuídos.
    
    Regras:
    1. Cada processo mantém um contador local
    2. Antes de qualquer evento local, incrementa o contador
    3. Ao enviar mensagem, inclui o valor atual do contador
    4. Ao receber mensagem com timestamp T, atualiza: contador = max(contador, T) + 1
    """
    
    def __init__(self):
        self.time = 0
        self.lock = threading.Lock()
    
    def increment(self):
        """Incrementa o relógio antes de um evento local ou envio de mensagem"""
        with self.lock:
            self.time += 1
            return self.time
    
    def update(self, received_time):
        """Atualiza o relógio ao receber uma mensagem: time = max(time, received_time) + 1"""
        with self.lock:
            self.time = max(self.time, received_time) + 1
            return self.time
    
    def get_time(self):
        """Retorna o valor atual do relógio"""
        with self.lock:
            return self.time


class TwoPhaseCommitServicer(aco_distributed_pb2_grpc.TwoPhaseCommitServiceServicer):
    """Implementacao do servico 2PC no worker (participante)"""
    
    def __init__(self, worker):
        self.worker = worker
    
    def Prepare(self, request, context):
        """Fase 1: Worker vota se esta pronto para commitar"""
        # Atualiza relógio de Lamport ao receber PREPARE
        received_time = request.timestamp
        current_time = self.worker.lamport_clock.update(received_time)
        
        print(f"\n[2PC] Recebi PREPARE para transacao {request.transaction_id} | Lamport: {current_time}")
        
        # Verifica se worker esta pronto (terminou de executar formigas)
        is_ready = self.worker.is_ready_for_commit()
        
        # Incrementa antes de enviar resposta
        response_time = self.worker.lamport_clock.increment()
        
        if is_ready:
            print(f"[2PC] Votando: YES (pronto para commitar)")
            return aco_distributed_pb2.PrepareResponse(
                vote_yes=True,
                worker_id=self.worker.worker_id,
                message="Pronto para commitar",
                solutions_count=self.worker.solutions_sent,
                timestamp=response_time
            )
        else:
            print(f"[2PC] Votando: NO (ainda processando)")
            return aco_distributed_pb2.PrepareResponse(
                vote_yes=False,
                worker_id=self.worker.worker_id,
                message="Ainda executando formigas",
                solutions_count=0,
                timestamp=response_time
            )
    
    def Commit(self, request, context):
        """Fase 2: Mestre ordenou COMMIT"""
        # Atualiza relógio de Lamport ao receber COMMIT
        received_time = request.timestamp if hasattr(request, 'timestamp') and request.timestamp > 0 else 0
        if received_time > 0:
            current_time = self.worker.lamport_clock.update(received_time)
        else:
            current_time = self.worker.lamport_clock.increment()
        
        print(f"\n[2PC] Recebi COMMIT para transacao {request.transaction_id} | Lamport: {current_time}")
        
        # Salva novos feromonios recebidos do mestre
        n = request.matrix_size
        self.worker.pheromone_cache = [
            [request.updated_pheromone_matrix[i*n + j] for j in range(n)]
            for i in range(n)
        ]
        
        print(f"[2PC] Feromonios atualizados localmente")
        print(f"[2PC] Transacao {request.transaction_id} COMMITADA")
        
        # Reseta estado para proxima iteracao
        self.worker.solutions_sent = 0
        self.worker.ready_for_commit = False
        
        # Incrementa antes de enviar resposta
        response_time = self.worker.lamport_clock.increment()
        
        return aco_distributed_pb2.CommitResponse(
            acknowledged=True,
            worker_id=self.worker.worker_id,
            message="Commit realizado com sucesso",
            timestamp=response_time
        )
    
    def Abort(self, request, context):
        """Fase 2: Mestre ordenou ABORT"""
        # Atualiza relógio de Lamport ao receber ABORT
        received_time = request.timestamp if hasattr(request, 'timestamp') and request.timestamp > 0 else 0
        if received_time > 0:
            current_time = self.worker.lamport_clock.update(received_time)
        else:
            current_time = self.worker.lamport_clock.increment()
        
        print(f"\n[2PC] Recebi ABORT para transacao {request.transaction_id} | Lamport: {current_time}")
        print(f"[2PC] Motivo: {request.reason}")
        
        # Descarta solucoes da iteracao atual (se houver)
        self.worker.solutions_sent = 0
        self.worker.ready_for_commit = False
        
        print(f"[2PC] Transacao {request.transaction_id} ABORTADA")
        print(f"[2PC] Estado resetado para proxima iteracao")
        
        # Incrementa antes de enviar resposta
        response_time = self.worker.lamport_clock.increment()
        
        return aco_distributed_pb2.AbortResponse(
            acknowledged=True,
            worker_id=self.worker.worker_id,
            message="Abort reconhecido",
            timestamp=response_time
        )


class ACOWorker:
    
    def __init__(self, worker_id, master_address, worker_port):
        self.worker_id = worker_id
        self.master_address = master_address
        self.worker_port = worker_port
        
        # Relógio de Lamport
        self.lamport_clock = LamportClock()
        
        # Estado para 2PC
        self.solutions_sent = 0
        self.ready_for_commit = False
        self.pheromone_cache = None
        
        # Conecta ao mestre
        self.master_channel = grpc.insecure_channel(master_address)
        self.master_stub = aco_distributed_pb2_grpc.ACOMasterServiceStub(self.master_channel)
        
        # Inicia servidor gRPC para receber chamadas 2PC do mestre
        self._start_grpc_server()
        
        print(f"\n{'='*60}")
        print(f"  WORKER {self.worker_id} INICIADO COM 2PC")
        print(f"  Conectado ao mestre: {master_address}")
        print(f"  Servidor 2PC na porta: {worker_port}")
        print(f"{'='*60}\n")
    
    def _start_grpc_server(self):
        """Inicia servidor gRPC para receber mensagens 2PC do mestre"""
        self.grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=5))
        aco_distributed_pb2_grpc.add_TwoPhaseCommitServiceServicer_to_server(
            TwoPhaseCommitServicer(self), 
            self.grpc_server
        )
        self.grpc_server.add_insecure_port(f'[::]:{self.worker_port}')
        self.grpc_server.start()
        print(f"[Worker {self.worker_id}] Servidor 2PC iniciado na porta {self.worker_port}")
    
    def is_ready_for_commit(self):
        """Verifica se worker esta pronto para commitar"""
        return self.ready_for_commit
    
    def run_ant(self, pheromone, distance_matrix, n, alpha, beta, start_node):
        visited = [start_node]
        total_cost = 0
        current = start_node
        
        while len(visited) < n:
            neighbors = []
            for j in range(n):
                if j != current and j not in visited and distance_matrix[current][j] > 0:
                    neighbors.append(j)
            
            if not neighbors:
                break
            
            probs = []
            for next_node in neighbors:
                tau = pheromone[current][next_node] ** alpha
                eta = (1.0 / distance_matrix[current][next_node]) ** beta
                probs.append(tau * eta)
            
            total = sum(probs)
            if total == 0:
                next_node = random.choice(neighbors)
            else:
                prob_norm = [p / total for p in probs]
                next_node = random.choices(neighbors, weights=prob_norm, k=1)[0]
            
            visited.append(next_node)
            total_cost += distance_matrix[current][next_node]
            current = next_node
        
        if len(visited) == n:
            total_cost += distance_matrix[current][start_node]
        
        return visited, total_cost
    
    def request_work(self):
        try:
            # Incrementa relógio antes de enviar requisição
            current_time = self.lamport_clock.increment()
            
            request = aco_distributed_pb2.WorkRequest(
                worker_id=self.worker_id,
                timestamp=current_time
            )
            
            response = self.master_stub.RequestWork(request)
            
            # Atualiza relógio ao receber resposta
            if hasattr(response, 'timestamp') and response.timestamp > 0:
                updated_time = self.lamport_clock.update(response.timestamp)
                print(f"[Worker {self.worker_id}] Relógio atualizado: {updated_time} (recebido: {response.timestamp})")
            
            return response
            
        except grpc.RpcError as e:
            print(f"[Worker {self.worker_id}] ERRO ao solicitar trabalho: {e.code()}")
            return None
    
    def submit_solution(self, path, cost, iteration):
        try:
            # Incrementa relógio antes de enviar solução
            current_time = self.lamport_clock.increment()
            
            solution = aco_distributed_pb2.Solution(
                worker_id=self.worker_id,
                path=path,
                cost=cost,
                iteration=iteration,
                timestamp=current_time
            )
            
            print(f"[Worker {self.worker_id}] Enviando solução | Lamport: {current_time} | Custo: {cost:.2f}")
            
            response = self.master_stub.SubmitSolution(solution)
            
            # Atualiza relógio ao receber resposta
            if hasattr(response, 'timestamp') and response.timestamp > 0:
                self.lamport_clock.update(response.timestamp)
            
            print(f"[Worker {self.worker_id}] Solução aceita! Melhor custo global: {response.current_best_cost:.2f}")
            return response
            
        except grpc.RpcError as e:
            print(f"[Worker {self.worker_id}] ERRO ao enviar solução: {e.code()}")
            return None
    
    def run(self):
        print(f"[Worker {self.worker_id}] Iniciando execucao...\n")
        
        iteration_count = 0
        
        while True:
            # Reseta estado para nova iteracao
            self.ready_for_commit = False
            self.solutions_sent = 0
            
            work = self.request_work()
            
            if work is None:
                print(f"[Worker {self.worker_id}] Falha ao solicitar trabalho. Tentando novamente em 2s...")
                time.sleep(2)
                continue
            
            if work.finished:
                print(f"\n[Worker {self.worker_id}] Algoritmo finalizado pelo mestre!")
                break
            
            iteration_count += 1
            print(f"\n{'='*60}")
            print(f"  WORKER {self.worker_id} | ITERACAO {work.iteration + 1}")
            print(f"  Executando {work.num_ants} formiga(s)...")
            print(f"{'='*60}\n")
            
            n = work.matrix_size
            pheromone = [[work.pheromone_matrix[i * n + j] for j in range(n)] for i in range(n)]
            distance = [[work.distance_matrix[i * n + j] for j in range(n)] for i in range(n)]
            
            best_local_cost = float('inf')
            best_local_path = None
            
            for ant_num in range(work.num_ants):
                start_node = ant_num % n
                path, cost = self.run_ant(pheromone, distance, n, work.alpha, work.beta, start_node)
                
                print(f"[Worker {self.worker_id}] Formiga {ant_num + 1}/{work.num_ants} | Inicio: No {start_node} | Custo: {cost:.2f} | Caminho: {path}")
                
                if cost < best_local_cost:
                    best_local_cost = cost
                    best_local_path = path
            
            print(f"\n[Worker {self.worker_id}] Melhor solucao local: {best_local_cost:.2f}")
            print(f"[Worker {self.worker_id}] Enviando ao mestre...")
            
            response = self.submit_solution(best_local_path, best_local_cost, work.iteration)
            
            if response:
                self.solutions_sent += 1
                self.ready_for_commit = True
                print(f"[Worker {self.worker_id}] Pronto para 2PC (solucao enviada)")
            
            # Aguarda mestre executar 2PC
            # Worker fica esperando mensagens PREPARE/COMMIT/ABORT
            print(f"[Worker {self.worker_id}] Aguardando protocolo 2PC do mestre...")
            time.sleep(1.0)
        
        print(f"\n{'='*60}")
        print(f"  WORKER {self.worker_id} FINALIZADO")
        print(f"  Total de iteracoes participadas: {iteration_count}")
        print(f"{'='*60}\n")
        
        # Para servidor gRPC
        self.grpc_server.stop(grace=2)
    
    def close(self):
        if self.master_channel:
            self.master_channel.close()
            print(f"[Worker {self.worker_id}] Conexão com mestre encerrada.")


def main():
    parser = argparse.ArgumentParser(description='Worker ACO Distribuido com 2PC')
    parser.add_argument('--id', type=int, required=True, help='ID do worker')
    parser.add_argument('--master', type=str, default='localhost:50051', 
                       help='Endereco do mestre (padrao: localhost:50051)')
    parser.add_argument('--port', type=int, default=None,
                       help='Porta do servidor 2PC do worker (padrao: 50051 + ID)')
    
    args = parser.parse_args()
    
    # Se porta nao especificada, usa 50051 + worker_id
    worker_port = args.port if args.port else (50051 + args.id)
    
    worker = ACOWorker(args.id, args.master, worker_port)
    
    try:
        worker.run()
    except KeyboardInterrupt:
        print(f"\n[Worker {args.id}] Interrompido pelo usuario...")
    finally:
        worker.close()


if __name__ == '__main__':
    main()