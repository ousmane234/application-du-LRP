import pandas as pd
from pyscipopt import Model


def construire_modele(
    menages_path="data/processed/menages_cluster.csv",
    centres_path="data/processed/centres.csv",
    dist_path="data/processed/distances.csv",
    nb_vehicules=2,
    Q=20,
    Nmax=3,
    Dmax=2000,
):
    """Construit et retourne le modèle PySCIPOpt LRP ainsi que les variables."""

    menages = pd.read_csv(menages_path)
    centres = pd.read_csv(centres_path)
    dist_matrix = pd.read_csv(dist_path, index_col=0)

    # Forcer index et colonnes en str
    dist_matrix.index = dist_matrix.index.astype(str)
    dist_matrix.columns = dist_matrix.columns.astype(str)

    # Vérifications
    if "poids_dechets" not in menages.columns:
        raise ValueError("Colonne 'poids_dechets' absente de menages_cluster.csv")
    if "cluster" not in centres.columns:
        raise ValueError("Colonne 'cluster' absente de centres.csv")

    I = menages["id"].astype(str).tolist()
    J = centres["cluster"].astype(str).tolist()
    poids = dict(zip(menages["id"].astype(str), menages["poids_dechets"]))

    # Pré-extraire les distances dans un dict (évite le retour d'une Series)
    dist = {}
    for i in I:
        for j in J:
            val = dist_matrix.at[str(i), str(j)]
            if hasattr(val, "iloc"):
                val = val.iloc[0]
            dist[i, j] = float(val)

    model = Model("LRP")
    model.hideOutput(True)

    # --- Variables ---
    x = {}
    y = {}
    for i in I:
        for j in J:
            x[i, j] = model.addVar(vtype="B", name=f"x_{i}_{j}")
    for j in J:
        y[j] = model.addVar(vtype="B", name=f"y_{j}")

    # --- Contraintes ---

    # 1. Chaque ménage affecté à exactement un centre
    for i in I:
        model.addCons(sum(x[i, j] for j in J) == 1, name=f"affect_{i}")

    # 2. Affectation seulement si centre ouvert
    for i in I:
        for j in J:
            model.addCons(x[i, j] <= y[j], name=f"lien_{i}_{j}")

    # 3. Capacité des centres
    for j in J:
        model.addCons(
            sum(poids[i] * x[i, j] for i in I) <= Q * y[j],
            name=f"capa_{j}",
        )

    # 4. Nombre max de centres ouverts
    limite = min(Nmax, nb_vehicules)
    model.addCons(
        sum(y[j] for j in J) <= limite,
        name="budget_centres",
    )

    # 5. Distance max ménage → centre
    for i in I:
        for j in J:
            model.addCons(dist[i, j] * x[i, j] <= Dmax, name=f"dist_{i}_{j}")

    # --- Objectif ---
    model.setObjective(
        sum(dist[i, j] * x[i, j] for i in I for j in J),
        "minimize",
    )

    # FIX : retourner les variables séparément car PySCIPOpt
    # n'autorise pas l'ajout d'attributs dynamiques sur Model
    meta = {"x": x, "y": y, "I": I, "J": J}

    return model, meta