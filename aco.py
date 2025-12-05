import math
import random

class ACO:
    def __init__(self, graph, num_ants=10, alpha=1.0, beta=5.0, rho=0.5, q=100):
        self.graph = graph
        self.num_ants = num_ants
        self.alpha = alpha
        self.beta = beta
        self.rho = rho
        self.q = q

        n = graph.get_size()
        self.pheromone = [[1.0 for _ in range(n)] for _ in range(n)]

    def get_probability(self, i, j):
        tau = self.pheromone[i][j] ** self.alpha
        eta = (1.0 / self.graph.get_distance(i, j)) ** self.beta
        return tau * eta
    
    def run_ant(self, start_node=0):
        n = self.graph.get_size()
        visited = [start_node]
        total_cost = 0

        current = start_node

        while len(visited) < n:
            neighbors = [j for j in self.graph.get_neighbors(current) if j not in visited]

            probs = []
            for next_node in neighbors:
                probs.append(self.get_probability(current, next_node))
            
            total = sum(probs)
            if total == 0:
                next_node = random.choice(neighbors)
            else:
                prob_norm = [p / total for p in probs]
                next_node =  random.choices(neighbors, weights=prob_norm, k=1)[0]

            visited.append(next_node)
            total_cost += self.graph.get_distance(current, next_node)
            current = next_node

        total_cost += self.graph.get_distance(current, start_node)

        return visited, total_cost
    
    def update_pheromones(self, solutions):
        n = self.graph.get_size()

        for i in range(n):
            for j in range(n):
                self.pheromone[i][j] *= (1 - self.rho)

        for path, cost in solutions:
            deposit = self.q / cost
            for idx in range(len(path)):
                i = path[idx]
                j = path[((idx + 1) % len(path))]
                self.pheromone[i][j] += deposit
                self.pheromone[j][i] += deposit

    def run_colony(self, interations=50):
        best_cost = math.inf
        best_path = None

        for it in range(interations):
            solutions = []
            for _ in range(self.num_ants):
                path, cost = self.run_ant()
                solutions.append((path, cost))
                if cost < best_cost:
                    best_cost = cost
                    best_path = path

            self.update_pheromones(solutions)
            print(f"Interação {it + 1}/{interations} | Melhor custo: {best_cost}")

        return best_path, best_cost