import time
import math
import argparse
import threading
from concurrent import futures
import grpc
import aco_distributed_pb2
import aco_distributed_pb2_grpc


class ACOMaster(aco_distributed_pb2_grpc.ACOMasterServiceServicer):
    """
    Servidor Mestre do ACO Distribuído
    Similar ao printer_server.py, mas coordena a execução distribuída do ACO
    """
    
    def __init__(self, graph_matrix, total_iterations=20, num_ants=10, alpha=1.0, beta=3.0, rho=0.5, q=10):
        self.distance_matrix = graph_matrix
        self.n = len(graph_matrix)
        self.total_iterations = total_iterations
        self.num_ants_per_worker = num_ants
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.q = q
        
        # Inicializa matriz de feromônios
        self.pheromone = [[1.0 for _ in range(self.n)] for _ in range(self.n)]
        
        # Controle de estado
        self.current_iteration = 0
        self.finished = False
        self.best_cost = math.inf
        self.best_path = None
        
        # Armazena soluções recebidas na iteração atual
        self.solutions_current_iteration = []
        self.workers_completed = set()
        
        # Lock para thread-safety
        self.lock = threading.Lock()
        
        print(f"\n{'='*70}")
        print(f"  MESTRE ACO INICIADO")
        print(f"  Tamanho do grafo: {self.n} nós")
        print(f"  Iterações totais: {self.total_iterations}")
        print(f"  Formigas por worker: {self.num_ants_per_worker}")
        print(f"  Alpha: {self.alpha} | Beta: {self.beta} | Rho: {self.rho} | Q: {self.q}")
        print(f"{'='*70}\n")
    
    def RequestWork(self, request, context):
        """Worker solicita trabalho ao mestre"""
        with self.lock:
            worker_id = request.worker_id
            
            print(f"[Mestre] Worker {worker_id} solicitou trabalho (Iteração {self.current_iteration + 1}/{self.total_iterations})")
            
            if self.finished:
                # Algoritmo terminou
                return aco_distributed_pb2.WorkAssignment(
                    finished=True,
                    num_ants=0,
                    iteration=self.current_iteration
                )
            
            # Prepara atribuição de trabalho
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
        """Worker envia solução encontrada"""
        with self.lock:
            worker_id = request.worker_id
            path = list(request.path)
            cost = request.cost
            iteration = request.iteration
            
            print(f"[Mestre] Worker {worker_id} enviou solução | Iteração: {iteration} | Custo: {cost:.2f}")
            
            # Armazena solução
            self.solutions_current_iteration.append((path, cost))
            self.workers_completed.add(worker_id)
            
            # Atualiza melhor solução global
            if cost < self.best_cost:
                self.best_cost = cost
                self.best_path = path
                print(f"[Mestre] *** NOVA MELHOR SOLUÇÃO *** | Custo: {cost:.2f} | Caminho: {path}")
            
            # Prepara resposta
            response = aco_distributed_pb2.SolutionResponse(
                accepted=True,
                current_best_cost=self.best_cost,
                current_best_path=self.best_path if self.best_path else [],
                message=f"Solução recebida do Worker {worker_id}"
            )
            
            return response
    
    def _update_pheromones(self):
        """Atualiza matriz de feromônios com as soluções coletadas"""
        print(f"\n[Mestre] Atualizando feromônios com {len(self.solutions_current_iteration)} soluções...")
        
        # Evaporação
        for i in range(self.n):
            for j in range(self.n):
                self.pheromone[i][j] *= (1 - self.rho)
        
        # Deposição de feromônio
        for path, cost in self.solutions_current_iteration:
            deposit = self.q / cost
            for idx in range(len(path)):
                i = path[idx]
                j = path[(idx + 1) % len(path)]
                self.pheromone[i][j] += deposit
                self.pheromone[j][i] += deposit
        
        print(f"[Mestre] Feromônios atualizados!")
    
    def run_coordination(self, expected_workers=2):
        """
        Loop principal de coordenação
        Aguarda workers enviarem soluções e coordena iterações
        """
        print(f"[Mestre] Aguardando {expected_workers} worker(s) para começar...\n")
        
        while self.current_iteration < self.total_iterations:
            iteration_start = time.time()
            
            print(f"\n{'='*70}")
            print(f"  ITERAÇÃO {self.current_iteration + 1}/{self.total_iterations}")
            print(f"  Melhor custo global: {self.best_cost if self.best_cost != math.inf else 'N/A'}")
            print(f"{'='*70}\n")
            
            # Aguarda workers enviarem soluções
            self._wait_for_workers(expected_workers)
            
            # Atualiza feromônios
            with self.lock:
                self._update_pheromones()
                
                # Prepara próxima iteração
                self.solutions_current_iteration.clear()
                self.workers_completed.clear()
                self.current_iteration += 1
            
            iteration_time = time.time() - iteration_start
            print(f"\n[Mestre] Iteração completada em {iteration_time:.2f}s\n")
        
        # Finaliza algoritmo
        with self.lock:
            self.finished = True
        
        print(f"\n{'='*70}")
        print(f"  ALGORITMO FINALIZADO!")
        print(f"  Melhor custo: {self.best_cost:.2f}")
        print(f"  Melhor caminho: {self.best_path}")
        print(f"{'='*70}\n")
    
    def _wait_for_workers(self, expected_workers, timeout=60):
        """Aguarda workers enviarem suas soluções"""
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
    """Inicia servidor gRPC do mestre"""
    master = ACOMaster(
        graph_matrix=graph_matrix,
        total_iterations=iterations,
        num_ants=ants
    )
    
    # Cria servidor gRPC
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    aco_distributed_pb2_grpc.add_ACOMasterServiceServicer_to_server(master, server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    
    print(f"[Mestre] Servidor gRPC iniciado na porta {port}\n")
    
    # Inicia coordenação em thread separada
    coordination_thread = threading.Thread(
        target=master.run_coordination,
        args=(workers,),
        daemon=True
    )
    coordination_thread.start()
    
    try:
        coordination_thread.join()  # Aguarda término do algoritmo
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
    
    # Grafo de exemplo (mesmo do main.py original)
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

