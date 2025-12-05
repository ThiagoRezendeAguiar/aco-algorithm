from aco import ACO
from graph import Graph

def main():
    distances = [
        [0, 2, 2, 5, 7],
        [2, 0, 4, 8, 2],
        [2, 4, 0, 1, 3],
        [5, 8, 1, 0, 2],
        [7, 2, 3, 2, 0],
    ]

    graph = Graph(distances)
    aco = ACO(
        graph=graph,
        num_ants=10,
        alpha=1.0,  # peso do feromônio
        beta=3.0,   # peso heurístico
        rho=0.5,    # taxa de evaporação
        q=10       # quantidade de feromônio
    )

    best_path, best_cost = aco.run_colony(20)

    print("Caminho: ", best_path)
    print("Custo: ", best_cost)

if __name__ == "__main__": 
    main()