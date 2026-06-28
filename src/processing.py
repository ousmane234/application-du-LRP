## Préparation des données ménages : coordonnées et clustering
import pandas as pd
from sklearn.cluster import KMeans
import os


def charger_donnees(path="data/raw/menages.csv"):
    """Charge les données depuis le fichier menages.csv."""
    df = pd.read_csv(path)
    # Créer une colonne id si absente
    if "id" not in df.columns:
        df["id"] = range(len(df))
    # Créer poids_dechets si absent (valeur par défaut 1)
    if "poids_dechets" not in df.columns:
        df["poids_dechets"] = 1.0
    return df


def clustering_menage(df, k=3):
    """Applique KMeans pour regrouper les ménages en clusters."""
    coords = df[["longitude", "latitude"]].values
    kmeans = KMeans(n_clusters=k, random_state=42).fit(coords)
    df = df.copy()
    df["cluster"] = kmeans.labels_
    centres = pd.DataFrame(
        kmeans.cluster_centers_, columns=["longitude", "latitude"]
    )
    # FIX : colonne nommée "cluster" (sans s) pour cohérence dans tout le projet
    centres["cluster"] = centres.index
    return df, centres


def sauvegarde_resultats(df, centres, out_path="data/processed/"):
    """Sauvegarde les ménages avec les clusters et les barycentres."""
    os.makedirs(out_path, exist_ok=True)
    df.to_csv(os.path.join(out_path, "menages_cluster.csv"), index=False)
    centres.to_csv(os.path.join(out_path, "centres.csv"), index=False)


if __name__ == "__main__":
    df = charger_donnees()
    df, centres = clustering_menage(df, k=3)
    sauvegarde_resultats(df, centres)
    print("===== prétraitement ==== OK")