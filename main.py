from src.processing import charger_donnees, clustering_menage, sauvegarde_resultats
from src.routing import construire_graphe, calculer_distances, sauvegarder_distances
from src.model import construire_modele
from src.solveur import resoudre_modele
from src.visualisation import afficher_resultats
import pandas as pd


def main():
    # --- Étape 1 : Prétraitement ---
    print("== Étape 1 : Chargement et clustering ==")
    df = charger_donnees("data/raw/menages.csv")
    df, centres = clustering_menage(df, k=3)
    sauvegarde_resultats(df, centres)

    # --- Étape 2 : Routage ---
    print("== Étape 2 : Construction du graphe et distances ==")
    G = construire_graphe("Dakar, Senegal")

    centres_points = centres[["cluster", "longitude", "latitude"]].rename(
        columns={"cluster": "id"}
    )
    points = pd.concat([df[["id", "longitude", "latitude"]], centres_points])
    # FIX : réutiliser dist_matrix en mémoire, pas besoin de relire le CSV
    dist_matrix = calculer_distances(G, points)
    sauvegarder_distances(dist_matrix)

    # --- Étape 3 : Modélisation et résolution (PySCIPOpt) ---
    print("== Étape 3 : Optimisation LRP ==")
    model = construire_modele(
        menages_path="data/processed/menages_cluster.csv",
        centres_path="data/processed/centres.csv",
        dist_path="data/processed/distances.csv",
        nb_vehicules=2,
        Q=20,
        Nmax=3,
        Dmax=2000,
    )
    solution = resoudre_modele(model)

    print("Centres ouverts :", solution["centres"])
    print("Coût total      :", solution["cout_total"])

    # --- Étape 4 : Visualisation ---
    print("== Étape 4 : Visualisation ==")
    afficher_resultats()

    print("\n===== Pipeline LRP terminé avec succès =====")


if __name__ == "__main__":
    main()