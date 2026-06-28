import osmnx as ox
import networkx as nx
import pandas as pd
import os


def charger_points(
    menage_path="data/processed/menages_cluster.csv",
    centres_path="data/processed/centres.csv",
):
    menages = pd.read_csv(menage_path)
    centres = pd.read_csv(centres_path)
    return menages, centres


def construire_graphe(place="Dakar, Senegal"):
    """Construit le graphe routier OSM pour la zone donnée."""
    G = ox.graph_from_place(place, network_type="drive")
    G = ox.distance.add_edge_lengths(G)
    return G


def calculer_distances(G, points):
    """Calcule la matrice de distances routières entre tous les points."""
    points = points.copy()
    points["node"] = ox.distance.nearest_nodes(
        G, points["longitude"].values, points["latitude"].values
    )

    ids = list(points["id"].astype(str))
    nodes = list(points["node"])

    dist_matrix = pd.DataFrame(index=ids, columns=ids, dtype=float)

    # FIX perf : Dijkstra par source au lieu de O(n²) appels shortest_path
    for i_idx, (i, ni) in enumerate(zip(ids, nodes)):
        lengths = nx.single_source_dijkstra_path_length(G, ni, weight="length")
        for j, nj in zip(ids, nodes):
            dist_matrix.loc[i, j] = lengths.get(nj, float("inf"))

    return dist_matrix


def sauvegarder_distances(dist_matrix, out_path="data/processed/"):
    os.makedirs(out_path, exist_ok=True)
    dist_matrix.to_csv(os.path.join(out_path, "distances.csv"))


if __name__ == "__main__":
    menages, centres = charger_points()
    G = construire_graphe()
    centres_points = centres[["cluster", "longitude", "latitude"]].rename(
        columns={"cluster": "id"}
    )
    points = pd.concat([menages[["id", "longitude", "latitude"]], centres_points])
    dist_matrix = calculer_distances(G, points)
    sauvegarder_distances(dist_matrix)
    print("=== Calcul et sauvegarde des distances === OK")