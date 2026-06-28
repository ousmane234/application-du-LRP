import pandas as pd
import os


def resoudre_modele(model, meta, out_path="output/tables/"):
    """Résout le modèle LRP avec PySCIPOpt et sauvegarde les résultats."""

    model.optimize()

    status = model.getStatus()
    if status not in ("optimal", "bestsolfound"):
        raise RuntimeError(
            f"Pas de solution acceptable — statut PySCIPOpt : {status}"
        )

    print(f"✅ Solution trouvée — statut : {status}")

    x = meta["x"]
    y = meta["y"]
    I = meta["I"]
    J = meta["J"]

    centres_ouverts = [j for j in J if (model.getVal(y[j]) or 0) > 0.5]
    affectations = [
        (i, j)
        for i in I
        for j in J
        if (model.getVal(x[i, j]) or 0) > 0.5
    ]
    cout_total = model.getObjVal()

    os.makedirs(out_path, exist_ok=True)
    pd.DataFrame({"centre_ouvert": centres_ouverts}).to_csv(
        os.path.join(out_path, "centres_ouverts.csv"), index=False
    )
    pd.DataFrame(affectations, columns=["menage", "centre"]).to_csv(
        os.path.join(out_path, "affectations.csv"), index=False
    )
    pd.DataFrame({"cout_total": [cout_total]}).to_csv(
        os.path.join(out_path, "cout_total.csv"), index=False
    )

    print(f"Coût total : {cout_total:.2f}")

    return {
        "centres": centres_ouverts,
        "affectations": affectations,
        "cout_total": cout_total,
    }