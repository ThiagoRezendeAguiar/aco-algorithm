class Graph:
    def __init__(self, adj_matrix):
        self.adj_matrix = adj_matrix
        self.n = len(adj_matrix)

    def get_distance(self, i, j):
        return self.adj_matrix[i][j]
    
    def get_neighbors(self, i):
        return [j for j in range(self.n) if j != i and self.adj_matrix[i][j] > 0]
    
    def get_size(self):
        return self.n