import matplotlib.pyplot as plt
import os
import numpy as np


TEST_DATA = {
    "nodes": [5, 10, 12, 14],
    
    "bf_times":  [6.0825, 12.8241, 21.0194, None],
    "aco_times": [13.0797, 14.0866, 15.0797, 16.0923],
    
    "bf_costs":  [9.0, 74.0, 127.00, None],
    "aco_costs": [9.0, 74.00, 131.00, 113.00]
}

OUTPUT_DIR = "./results"

def ensure_dir():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Diretório '{OUTPUT_DIR}' criado.")

def plot_results_table():
    nodes = TEST_DATA["nodes"]
    
    cell_text = []
    for i, n in enumerate(nodes):
        # Formatação do BF
        bf_t = f"{TEST_DATA['bf_times'][i]:.4f}s" if TEST_DATA['bf_times'][i] is not None else "TIMEOUT"
        bf_c = f"{TEST_DATA['bf_costs'][i]:.1f}" if TEST_DATA['bf_costs'][i] is not None else "-"
        
        # Formatação do ACO
        aco_t = f"{TEST_DATA['aco_times'][i]:.4f}s"
        aco_c = f"{TEST_DATA['aco_costs'][i]:.1f}"
        
        # Comparação de Custo (Gap)
        if TEST_DATA['bf_costs'][i] and TEST_DATA['aco_costs'][i]:
            gap = ((TEST_DATA['aco_costs'][i] - TEST_DATA['bf_costs'][i]) / TEST_DATA['bf_costs'][i]) * 100
            gap_str = f"{gap:.1f}%"
        else:
            gap_str = "N/A"

        row = [f"{n} nós", bf_t, aco_t, bf_c, aco_c, gap_str]
        cell_text.append(row)

    columns = ["Grafo", "Tempo BF", "Tempo ACO", "Custo BF", "Custo ACO", "Gap (%)"]
    
    # Configura o Plot (sem eixos, apenas tabela)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.axis('tight')
    ax.axis('off')
    
    # Desenha a tabela
    table = ax.table(cellText=cell_text, colLabels=columns, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.5) # Ajusta escala (largura, altura das células)
    
    # Estilizando cabeçalho
    for (row, col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(weight='bold')
            cell.set_facecolor('#e6e6e6')

    plt.title("Comparativo: Brute Force vs ACO Distribuído", pad=20, weight='bold')
    
    filepath = os.path.join(OUTPUT_DIR, "tabela_resultados.png")
    plt.savefig(filepath, dpi=300, bbox_inches='tight')
    print(f"Tabela salva em: {filepath}")
    plt.close()

def plot_execution_time():
    """Gera gráfico comparativo de tempo"""
    nodes = TEST_DATA["nodes"]
    bf_times = TEST_DATA["bf_times"]
    aco_times = TEST_DATA["aco_times"]
    
    # Filtra dados None para o gráfico não quebrar
    valid_bf_indices = [i for i, v in enumerate(bf_times) if v is not None]
    valid_bf_nodes = [nodes[i] for i in valid_bf_indices]
    valid_bf_times = [bf_times[i] for i in valid_bf_indices]

    plt.figure(figsize=(10, 6))
    
    # Plot BF
    plt.plot(valid_bf_nodes, valid_bf_times, marker='o', color='red', label='Brute Force (Exato)', linestyle='--', linewidth=2)
    
    # Plot ACO
    plt.plot(nodes, aco_times, marker='s', color='green', label='ACO Distribuído (Heurística)', linewidth=2)
    
    plt.xlabel('Tamanho do Grafo (Número de Cidades)', fontsize=12)
    plt.ylabel('Tempo de Execução (segundos)', fontsize=12)
    plt.title('Escalabilidade: Força Bruta vs ACO', fontsize=14, weight='bold')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend()
    
    # Anotação para mostrar a explosão combinatória
    if len(valid_bf_times) > 0:
        plt.annotate('Explosão Combinatória!', 
                     xy=(valid_bf_nodes[-1], valid_bf_times[-1]), 
                     xytext=(valid_bf_nodes[-1]-2, valid_bf_times[-1]),
                     arrowprops=dict(facecolor='black', shrink=0.05))
    
    filepath = os.path.join(OUTPUT_DIR, "grafico_tempo.png")
    plt.savefig(filepath, dpi=300)
    print(f"Gráfico salvo em: {filepath}")
    plt.close()

if __name__ == "__main__":
    ensure_dir()
    plot_results_table()
    plot_execution_time()
    print("\nProcesso concluído! Verifique a pasta ./results/")