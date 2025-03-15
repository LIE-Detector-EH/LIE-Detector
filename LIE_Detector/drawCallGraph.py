import networkx as nx
import matplotlib.pyplot as plt

def draw_call_graph(call_graph: nx.DiGraph, output_path: str = "call_graph.png"):
    plt.figure(figsize=(12, 12))


    pos = nx.spring_layout(call_graph, k=0.5, iterations=50)


    nx.draw_networkx_nodes(call_graph, pos, node_size=500, node_color='lightblue')


    nx.draw_networkx_edges(call_graph, pos, arrowstyle='->', arrowsize=20, edge_color='gray')


    nx.draw_networkx_labels(call_graph, pos, font_size=8, font_family='sans-serif')

    plt.title("Function Call Graph")
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(output_path, format="PNG")
    plt.show()
    print(f"Call graph saved to {output_path}.")
