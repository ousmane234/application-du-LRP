import streamlit as st
import pandas as pd
from streamlit_folium import st_folium
import folium

from src.processing import charger_donnees, clustering_menage, sauvegarde_resultats
from src.routing import construire_graphe, calculer_distances, sauvegarder_distances
from src.model import construire_modele
from src.solveur import resoudre_modele

st.set_page_config(page_title="LRP - Collecte de déchets", layout="wide")
st.title("🚛 Application LRP - Collecte de déchets à Dakar")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📂 Données", "🔹 Clustering", "⚡ Optimisation", "🌍 Résultats"]
)


@st.cache_resource
def charger_graphe(place):
    return construire_graphe(place)


# ─────────────────────────────────────────
# Onglet 1 — Données
# ─────────────────────────────────────────
with tab1:
    st.header("Chargement des données")
    uploaded_file = st.file_uploader("Charger un fichier CSV de ménages", type="csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        if "id" not in df.columns:
            df["id"] = range(len(df))
        if "poids_dechets" not in df.columns:
            df["poids_dechets"] = 1.0
            st.info("Colonne 'poids_dechets' absente — valeur par défaut 1.0 appliquée.")
        st.write("✅ Données chargées :", df.head())
        st.session_state["df"] = df


# ─────────────────────────────────────────
# Onglet 2 — Clustering
# ─────────────────────────────────────────
with tab2:
    st.header("Clustering des ménages")
    if "df" not in st.session_state:
        st.warning("Veuillez d'abord charger des données dans l'onglet Données.")
    else:
        k = st.slider("Nombre de clusters (points candidats)", min_value=2, max_value=10, value=3)
        if st.button("Lancer le clustering"):
            with st.spinner("Clustering en cours..."):
                df, centres = clustering_menage(st.session_state["df"], k)
                sauvegarde_resultats(df, centres)
                st.session_state["df_cluster"] = df
                st.session_state["centres"] = centres
            st.success("Clustering terminé ✅")
            st.map(df[["latitude", "longitude"]])


# ─────────────────────────────────────────
# Onglet 3 — Optimisation
# ─────────────────────────────────────────
with tab3:
    st.header("Optimisation LRP")
    if "df_cluster" not in st.session_state or "centres" not in st.session_state:
        st.warning("Veuillez d'abord effectuer le clustering dans l'onglet Clustering.")
    else:
        nb_vehicules = st.number_input("Nombre de véhicules", min_value=1, max_value=10, value=2)
        Q = st.number_input("Capacité d'un centre (Q)", min_value=1, value=20)
        Nmax = st.number_input("Nombre max de centres ouverts", min_value=1, value=3)
        Dmax = st.number_input("Distance max ménage→centre (m)", min_value=100, value=2000)

        if st.button("Lancer l'optimisation"):
            with st.spinner("Construction du graphe routier (peut prendre 1-2 min)..."):
                G = charger_graphe("Dakar, Senegal")

            with st.spinner("Calcul des distances..."):
                centres_points = st.session_state["centres"][
                    ["cluster", "longitude", "latitude"]
                ].rename(columns={"cluster": "id"})
                points = pd.concat([
                    st.session_state["df_cluster"][["id", "longitude", "latitude"]],
                    centres_points,
                ])
                dist_matrix = calculer_distances(G, points)
                sauvegarder_distances(dist_matrix)

            with st.spinner("Résolution du modèle (PySCIPOpt)..."):
                try:
                    model, meta = construire_modele(
                        menages_path="data/processed/menages_cluster.csv",
                        centres_path="data/processed/centres.csv",
                        dist_path="data/processed/distances.csv",
                        nb_vehicules=int(nb_vehicules),
                        Q=int(Q),
                        Nmax=int(Nmax),
                        Dmax=int(Dmax),
                    )
                    solution = resoudre_modele(model, meta)
                    st.session_state["solution"] = solution
                    st.success("Optimisation terminée ✅")
                    st.write("**Centres ouverts :**", solution["centres"])
                    st.write("**Coût total :**", round(solution["cout_total"], 2))
                except RuntimeError as e:
                    st.error(f"Erreur solveur : {e}")


# ─────────────────────────────────────────
# Onglet 4 — Résultats
# ─────────────────────────────────────────
with tab4:
    st.header("Visualisation des résultats")
    if "solution" not in st.session_state:
        st.warning("Veuillez d'abord lancer l'optimisation dans l'onglet Optimisation.")
    else:
        if st.button("Afficher la carte"):
            menages = st.session_state["df_cluster"]
            centres = st.session_state["centres"].copy()
            if "clusters" in centres.columns:
                centres = centres.rename(columns={"clusters": "cluster"})

            solution = st.session_state["solution"]
            centres_ouverts_vals = [str(c) for c in solution["centres"]]
            affectations = solution["affectations"]

            m = folium.Map(location=[14.6928, -17.4467], zoom_start=12)

            # Ménages
            for _, row in menages.iterrows():
                folium.CircleMarker(
                    location=[row["latitude"], row["longitude"]],
                    radius=3,
                    color="blue",
                    fill=True,
                    fill_opacity=0.6,
                    popup=f"Ménage {row['id']} - Cluster {row['cluster']}",
                ).add_to(m)

            # Centres
            for _, row in centres.iterrows():
                ouvert = str(row["cluster"]) in centres_ouverts_vals
                color = "green" if ouvert else "red"
                folium.Marker(
                    location=[row["latitude"], row["longitude"]],
                    icon=folium.Icon(color=color, icon="home"),
                    popup=f"Centre {row['cluster']} ({'Ouvert' if ouvert else 'Fermé'})",
                ).add_to(m)

            # Liaisons ménage → centre
            menages_idx = menages.set_index("id")
            centres_idx = centres.set_index("cluster")

            for (i, j) in affectations:
                try:
                    i_key = int(i) if str(i).isdigit() else i
                    j_key = int(j) if str(j).isdigit() else j
                    m_coord = menages_idx.loc[i_key, ["latitude", "longitude"]]
                    c_coord = centres_idx.loc[j_key, ["latitude", "longitude"]]
                    folium.PolyLine(
                        locations=[
                            [float(m_coord["latitude"]), float(m_coord["longitude"])],
                            [float(c_coord["latitude"]), float(c_coord["longitude"])],
                        ],
                        color="gray",
                        weight=1,
                        opacity=0.4,
                    ).add_to(m)
                except KeyError:
                    pass

            # Légende
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

            st_folium(m, width=900, height=600)