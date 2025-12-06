import time
import random
import argparse
import grpc
import aco_distributed_pb2
import aco_distributed_pb2_grpc


class ACOWorker:
    """
    Worker do ACO Distribuído
    Similar ao printing_client.py, mas mais simples (sem exclusão mútua)
    """
    
    def __init__(self, worker_id, master_address):
        self.worker_id = worker_id
        self.master_address = master_address
        self.timestamp = 0
        
        # Conecta ao mestre
        self.master_channel = grpc.insecure_channel(master_address)
        self.master_stub = aco_distributed_pb2_grpc.ACOMasterServiceStub(self.master_channel)
        
        print(f"\n{'='*60}")
        print(f"  WORKER {self.worker_id} INICIADO")
        print(f"  Conectado ao mestre: {master_address}")
        print(f"{'='*60}\n")
    
    def run_ant(self, pheromone, distance_matrix, n, alpha, beta, start_node=0):
        """
        Executa uma formiga (mesma lógica do aco.py original)
        """
        visited = [start_node]
        total_cost = 0
        current = start_node
        
        while len(visited) < n:
            # Encontra vizinhos não visitados
            neighbors = []
            for j in range(n):
                if j != current and j not in visited and distance_matrix[current][j] > 0:
                    neighbors.append(j)
            
            if not neighbors:
                break
            
            # Calcula probabilidades
            probs = []
            for next_node in neighbors:
                tau = pheromone[current][next_node] ** alpha
                eta = (1.0 / distance_matrix[current][next_node]) ** beta
                probs.append(tau * eta)
            
            # Seleciona próximo nó
            total = sum(probs)
            if total == 0:
                next_node = random.choice(neighbors)
            else:
                prob_norm = [p / total for p in probs]
                next_node = random.choices(neighbors, weights=prob_norm, k=1)[0]
            
            # Move para próximo nó
            visited.append(next_node)
            total_cost += distance_matrix[current][next_node]
            current = next_node
        
        # Retorna ao início
        if len(visited) == n:
            total_cost += distance_matrix[current][start_node]
        
        return visited, total_cost
    
    def request_work(self):
        """Solicita trabalho ao mestre"""
        try:
            self.timestamp += 1
            request = aco_distributed_pb2.WorkRequest(
                worker_id=self.worker_id,
                timestamp=self.timestamp
            )
            
            response = self.master_stub.RequestWork(request)
            return response
            
        except grpc.RpcError as e:
            print(f"[Worker {self.worker_id}] ERRO ao solicitar trabalho: {e.code()}")
            return None
    
    def submit_solution(self, path, cost, iteration):
        """Envia solução ao mestre"""
        try:
            self.timestamp += 1
            solution = aco_distributed_pb2.Solution(
                worker_id=self.worker_id,
                path=path,
                cost=cost,
                iteration=iteration,
                timestamp=self.timestamp
            )
            
            response = self.master_stub.SubmitSolution(solution)
            
            print(f"[Worker {self.worker_id}] Solução aceita! Melhor custo global: {response.current_best_cost:.2f}")
            return response
            
        except grpc.RpcError as e:
            print(f"[Worker {self.worker_id}] ERRO ao enviar solução: {e.code()}")
            return None
    
    def run(self):
        """Loop principal do worker"""
        print(f"[Worker {self.worker_id}] Iniciando execução...\n")
        
        iteration_count = 0
        
        while True:
            # Solicita trabalho ao mestre
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
            print(f"  WORKER {self.worker_id} | ITERAÇÃO {work.iteration + 1}")
            print(f"  Executando {work.num_ants} formiga(s)...")
            print(f"{'='*60}\n")
            
            # Reconstrói matrizes
            n = work.matrix_size
            pheromone = [[work.pheromone_matrix[i * n + j] for j in range(n)] for i in range(n)]
            distance = [[work.distance_matrix[i * n + j] for j in range(n)] for i in range(n)]
            
            # Executa formigas
            best_local_cost = float('inf')
            best_local_path = None
            
            for ant_num in range(work.num_ants):
                path, cost = self.run_ant(pheromone, distance, n, work.alpha, work.beta)
                
                print(f"[Worker {self.worker_id}] Formiga {ant_num + 1}/{work.num_ants} | Custo: {cost:.2f} | Caminho: {path}")
                
                if cost < best_local_cost:
                    best_local_cost = cost
                    best_local_path = path
            
            # Envia melhor solução local ao mestre
            print(f"\n[Worker {self.worker_id}] Melhor solução local: {best_local_cost:.2f}")
            print(f"[Worker {self.worker_id}] Enviando ao mestre...")
            
            self.submit_solution(best_local_path, best_local_cost, work.iteration)
            
            # Pequeno delay antes da próxima iteração
            time.sleep(0.5)
        
        print(f"\n{'='*60}")
        print(f"  WORKER {self.worker_id} FINALIZADO")
        print(f"  Total de iterações participadas: {iteration_count}")
        print(f"{'='*60}\n")
    
    def close(self):
        """Fecha conexão com o mestre"""
        if self.master_channel:
            self.master_channel.close()
            print(f"[Worker {self.worker_id}] Conexão com mestre encerrada.")


def main():
    parser = argparse.ArgumentParser(description='Worker ACO Distribuído')
    parser.add_argument('--id', type=int, required=True, help='ID do worker')
    parser.add_argument('--master', type=str, default='localhost:50051', 
                       help='Endereço do mestre (padrão: localhost:50051)')
    
    args = parser.parse_args()
    
    worker = ACOWorker(args.id, args.master)
    
    try:
        worker.run()
    except KeyboardInterrupt:
        print(f"\n[Worker {args.id}] Interrompido pelo usuário...")
    finally:
        worker.close()


if __name__ == '__main__':
    main()

