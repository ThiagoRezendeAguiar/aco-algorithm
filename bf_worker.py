import grpc
import time
import sys
import itertools
import bruteforce_pb2
import bruteforce_pb2_grpc

def calculate_path_cost(path, matrix):
    cost = 0
    for i in range(len(path) - 1):
        u = path[i]
        v = path[i+1]
        cost += matrix[u][v]
    # Fecha o ciclo (volta pro inicio)
    cost += matrix[path[-1]][path[0]]
    return cost

def run_worker(worker_id):
    channel = grpc.insecure_channel('localhost:50052')
    stub = bruteforce_pb2_grpc.BFServiceStub(channel)
    
    print(f"Worker {worker_id} conectado e pronto para força bruta...")

    while True:
        # 1. Pede tarefa
        try:
            task = stub.GetTask(bruteforce_pb2.BFRequest(worker_id=worker_id))
        except grpc.RpcError:
            print("Mestre indisponível. Encerrando.")
            break

        if task.finished:
            print("Sem mais tarefas. Encerrando.")
            break

        # 2. Prepara dados
        n = task.matrix_size
        matrix = []
        for i in range(n):
            row = task.distance_matrix[i*n : (i+1)*n]
            matrix.append(row)
        
        prefix = list(task.prefix) # Ex: [0, 2]
        
        # Descobre quais cidades faltam
        all_cities = set(range(n))
        visited_cities = set(prefix)
        missing_cities = list(all_cities - visited_cities)
        
        print(f"[Worker {worker_id}] Processando prefixo {prefix}. Faltam: {missing_cities}")
        
        # 3. Força Bruta Local (Permutação das cidades que faltam)
        best_local_cost = float('inf')
        best_local_path = []

        # Gera todas as permutações das cidades restantes
        # Ex: se faltam [1, 3], gera (1,3) e (3,1)
        for p in itertools.permutations(missing_cities):
            # Caminho completo = Prefixo + Permutação
            current_path = prefix + list(p)
            
            cost = calculate_path_cost(current_path, matrix)
            
            if cost < best_local_cost:
                best_local_cost = cost
                best_local_path = current_path

        # 4. Envia resultado
        print(f"[Worker {worker_id}] Melhor local: {best_local_path} com custo {best_local_cost}")
        stub.SubmitResult(bruteforce_pb2.BFResult(
            worker_id=worker_id,
            path=best_local_path,
            cost=best_local_cost
        ))
        
        time.sleep(1.0) # Simula delay de rede/processamento visual

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python bf_worker.py <worker_id>")
        sys.exit(1)
    run_worker(int(sys.argv[1]))