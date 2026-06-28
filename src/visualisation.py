import folium
import pandas as pd
import os


def afficher_resultats(
    menages_path="data/processed/menages_cluster.csv",
    centres_path="data/processed/centres.csv",
    affectations_path="output/tables/affectations.csv",
    centres_ouverts_path="output/tables/centres_ouverts.csv",
    out_path="output/figures/",
):
    """Affiche les résultats sur une carte interactive avec Folium."""

    menages = pd.read_csv(menages_path)
    centres = pd.read_csv(centres_path)
    affectations = pd.read_csv(affectations_path)
    centres_ouverts = pd.read_csv(centres_ouverts_path)

    # FIX héritage : normaliser le nom de colonne
    if "clusters" in centres.columns:
        centres = centres.rename(columns={"clusters": "cluster"})

    m = folium.Map(location=[14.6928, -17.4467], zoom_start=12)

    # --- Ménages ---
    for _, row in menages.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=3,
            color="blue",
            fill=True,
            fill_opacity=0.6,
            popup=f"Ménage {row['id']} - Cluster {row['cluster']}",
        ).add_to(m)

    # --- Centres ---
    for _, row in centres.iterrows():
        ouvert = row["cluster"] in centres_ouverts["centre_ouvert"].values
        color = "green" if ouvert else "red"
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            icon=folium.Icon(color=color, icon="home"),
            popup=f"Centre {row['cluster']} ({'Ouvert' if ouvert else 'Fermé'})",
        ).add_to(m)

    # FIX : tracer les liaisons ménage → centre
    menages_idx = menages.set_index("id")
    centres_idx = centres.set_index("cluster")

    for _, row in affectations.iterrows():
        try:
            m_coord = menages_idx.loc[row["menage"], ["latitude", "longitude"]]
            c_coord = centres_idx.loc[row["centre"], ["latitude", "longitude"]]
            folium.PolyLine(
                locations=[
                    [m_coord["latitude"], m_coord["longitude"]],
                    [c_coord["latitude"], c_coord["longitude"]],
                ],
                color="gray",
                weight=1,
                opacity=0.4,
            ).add_to(m)
        except KeyError:
            pass  # ménage ou centre introuvable, on ignore

    # --- Légende ---
    legend_html = """
    <div style="position:fixed; bottom:30px; left:30px; z-index:1000;
                background:white; padding:10px; border:1px solid grey;
                border-radius:5px; font-size:13px;">
      <b>Légende</b><br>
      🔵 Ménage<br>
      🟢 Centre ouvert<br>
      🔴 Centre fermé<br>
      ─ Affectation
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    os.makedirs(out_path, exist_ok=True)
    m.save(os.path.join(out_path, "resultats.html"))
    print("✅ Carte sauvegardée dans output/figures/resultats.html")

    return m