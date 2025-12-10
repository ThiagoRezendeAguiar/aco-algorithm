import grpc
from concurrent import futures
import time
import math
import argparse
import threading
import bruteforce_pb2
import bruteforce_pb2_grpc
from utils_gen_graphs import load_graph_from_json

class BFMaster(bruteforce_pb2_grpc.BFServiceServicer):
    def __init__(self, graph_matrix):
        self.matrix = graph_matrix
        self.n = len(graph_matrix)
        
        # Cria as tarefas: Fixa a cidade 0 e varia a segunda cidade
        # Ex: Tarefa 1 = Prefixo [0, 1], Tarefa 2 = Prefixo [0, 2]...
        # O Worker vai permutar o resto.
        self.tasks = []
        for i in range(1, self.n):
            self.tasks.append([0, i])
            
        self.total_tasks = len(self.tasks)
        self.lock = threading.Lock()
        
        self.best_global_path = []
        self.best_global_cost = math.inf
        
        self.start_time = time.time()
        self.completed_tasks = 0

        print(f"--- MASTER BRUTE FORCE INICIADO ---")
        print(f"Cidades: {self.n}")
        print(f"Tarefas geradas: {self.total_tasks} (Prefixos fixos)")
        print(f"-----------------------------------")

    def GetTask(self, request, context):
        with self.lock:
            if not self.tasks:
                return bruteforce_pb2.BFTask(finished=True)
            
            # Pega a próxima tarefa da fila
            prefix = self.tasks.pop(0)
            print(f"[Master] Enviando tarefa Prefixo {prefix} para Worker {request.worker_id}")
            
            # Achata a matriz para envio
            flat_matrix = [val for row in self.matrix for val in row]
            
            return bruteforce_pb2.BFTask(
                finished=False,
                prefix=prefix,
                distance_matrix=flat_matrix,
                matrix_size=self.n
            )

    def SubmitResult(self, request, context):
        with self.lock:
            self.completed_tasks += 1
            print(f"[Master] Recebido de Worker {request.worker_id}: Custo {request.cost:.2f}")
            
            if request.cost < self.best_global_cost:
                self.best_global_cost = request.cost
                self.best_global_path = list(request.path)
                print(f"[Master] *** NOVO MELHOR GLOBAL: {self.best_global_cost:.2f} ***")

            if self.completed_tasks == self.total_tasks:
                self.finalize()
                
            return bruteforce_pb2.BFAck(success=True)

    def finalize(self):
        duration = time.time() - self.start_time
        print(f"\n{'='*60}")
        print(f"FIM DO BRUTE FORCE DISTRIBUÍDO")
        print(f"Tempo Total: {duration:.4f} segundos")
        print(f"Melhor Custo: {self.best_global_cost:.2f}")
        print(f"Melhor Caminho: {self.best_global_path}")
        print(f"{'='*60}\n")

def serve():
    parser = argparse.ArgumentParser(description='Mestre Brute Force')
    parser.add_argument('--graph', type=str, default='graphs/5_nodes.json', help='Caminho do arquivo JSON do grafo')
    args = parser.parse_args()

    print(f"Carregando grafo de: {args.graph}")
    graph = load_graph_from_json(args.graph)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    master = BFMaster(graph)
    bruteforce_pb2_grpc.add_BFServiceServicer_to_server(master, server)
    server.add_insecure_port('[::]:50052') 
    server.start()
    print("Servidor rodando na porta 50052...")
    
    try:
        while master.completed_tasks < master.total_tasks:
            time.sleep(1)
        time.sleep(2) # Espera um pouco antes de matar o processo
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()