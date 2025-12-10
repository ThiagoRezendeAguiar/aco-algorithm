import os
import sys
import json
import random


def load_graph_from_json(file_path):
    try:
        with open(file_path, 'r') as f:
            matrix = json.load(f)
        return matrix
    except FileNotFoundError:
        print(f"ERRO: Arquivo '{file_path}' não encontrado.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"ERRO: Arquivo '{file_path}' não é um JSON válido.")
        sys.exit(1)
        
        

def generate_symmetric_matrix(n, min_weight=1, max_weight=50):
    # Cria matriz vazia NxN
    matrix = [[0 for _ in range(n)] for _ in range(n)]
    
    for i in range(n):
        for j in range(i + 1, n):
            weight = random.randint(min_weight, max_weight)
            matrix[i][j] = weight
            matrix[j][i] = weight # Garante simetria (A->B == B->A)
            
    return matrix

def save_graph(filename, matrix):
    filepath = os.path.join("graphs", filename)
    with open(filepath, 'w') as f:
        json.dump(matrix, f, indent=2)
    print(f"Gerado: {filepath}")

def main():
    if not os.path.exists("graphs"):
        os.makedirs("graphs")

    graph_5 = [ # grafo fixo
        [0, 2, 2, 5, 7],
        [2, 0, 4, 8, 2],
        [2, 4, 0, 1, 3],
        [5, 8, 1, 0, 2],
        [7, 2, 3, 2, 0],
    ]
    save_graph("5_nodes.json", graph_5)

    # 2. Grafo Médio (10 nós) - Brute Force leva alguns segundos/minutos
    graph_10 = generate_symmetric_matrix(10)
    save_graph("10_nodes.json", graph_10)

    # 3. Grafo Pesado para BF (12 nós) - Brute Force vai demorar bastante
    graph_12 = generate_symmetric_matrix(12)
    save_graph("12_nodes.json", graph_12)

    # 4. Grafo Impossível para BF (14 nós) - Só o ACO vai conseguir terminar em tempo hábil
    graph_14 = generate_symmetric_matrix(14)
    save_graph("14_nodes.json", graph_14)

if __name__ == "__main__":
    main()