import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import folium

from src.processing import charger_donnees, clustering_menage, sauvegarde_resultats
from src.routing import construire_graphe, calculer_distances, sauvegarder_distances
from src.model import construire_modele
from src.solveur import resoudre_modele

st.set_page_config(page_title="LRP — Collecte", layout="wide", page_icon="🚛")

# ─── CSS global ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Sidebar sombre */
[data-testid="stSidebar"] {
    background-color: #1e2130;
}
[data-testid="stSidebar"] * {
    color: #c9d1e0 !important;
}
/* Titre sidebar */
.sidebar-title {
    font-size: 1.3rem;
    font-weight: 700;
    color: #ffffff !important;
    padding: 1rem 0 1.5rem 0;
    border-bottom: 1px solid #3a3f55;
    margin-bottom: 1rem;
}
/* Cartes KPI */
.kpi-card {
    border-radius: 10px;
    padding: 1.2rem 1.5rem;
    color: white;
    margin-bottom: 1rem;
}
.kpi-card .kpi-value {
    font-size: 2rem;
    font-weight: 800;
    margin: 0;
}
.kpi-card .kpi-label {
    font-size: 0.85rem;
    opacity: 0.85;
    margin: 0;
}
.kpi-blue   { background: linear-gradient(135deg, #1a73e8, #0d47a1); }
.kpi-orange { background: linear-gradient(135deg, #f4a020, #e65c00); }
.kpi-green  { background: linear-gradient(135deg, #2e9e5b, #1b5e20); }
.kpi-purple { background: linear-gradient(135deg, #7c4dff, #4527a0); }
/* Section titres */
.section-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: #333;
    border-left: 4px solid #1a73e8;
    padding-left: 0.6rem;
    margin: 1.2rem 0 0.8rem 0;
}
/* Tableau */
.df-table { font-size: 0.88rem; }
/* Bouton export */
.stDownloadButton button {
    background-color: #1a73e8;
    color: white;
    border-radius: 6px;
    border: none;
    padding: 0.4rem 1rem;
}
</style>
""", unsafe_allow_html=True)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-title">🚛 LRP — Collecte</div>', unsafe_allow_html=True)
    page = st.radio(
        "",
        ["📂 Données", "🔹 Clustering", "⚡ Optimisation", "📊 Résultats"],
        label_visibility="collapsed"
    )


@st.cache_resource
def charger_graphe(place):
    return construire_graphe(place)


def construire_carte(menages, centres, solution):
    centres = centres.copy()
    if "clusters" in centres.columns:
        centres = centres.rename(columns={"clusters": "cluster"})

    centres_ouverts_vals = [str(c) for c in solution["centres"]]
    affectations = solution["affectations"]

    # Centrer sur les données
    lat_c = menages["latitude"].mean()
    lon_c = menages["longitude"].mean()
    m = folium.Map(location=[lat_c, lon_c], zoom_start=13, tiles="OpenStreetMap")

    # Ménages
    for _, row in menages.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=4,
            color="#1a73e8",
            fill=True,
            fill_color="#1a73e8",
            fill_opacity=0.7,
            popup=f"Ménage {row['id']}",
            tooltip=f"Ménage {row['id']}",
        ).add_to(m)

    # Centres
    for _, row in centres.iterrows():
        ouvert = str(row["cluster"]) in centres_ouverts_vals
        icon_color = "green" if ouvert else "red"
        icon_name = "home" if ouvert else "times"
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            icon=folium.Icon(color=icon_color, icon=icon_name, prefix="fa"),
            popup=f"Centre {row['cluster']} — {'Ouvert' if ouvert else 'Fermé'}",
            tooltip=f"Centre {row['cluster']}",
        ).add_to(m)

    # Liaisons ménage → centre (couleur par centre)
    palette = ["#1a73e8", "#f4a020", "#2e9e5b", "#7c4dff", "#e53935", "#00acc1"]
    centre_couleur = {j: palette[idx % len(palette)] for idx, j in enumerate(centres_ouverts_vals)}

    menages_idx = menages.set_index("id")
    centres_idx = centres.set_index("cluster")

    for (i, j) in affectations:
        try:
            i_key = int(i) if str(i).isdigit() else i
            j_key = int(j) if str(j).isdigit() else j
            m_coord = menages_idx.loc[i_key, ["latitude", "longitude"]]
            c_coord = centres_idx.loc[j_key, ["latitude", "longitude"]]
            couleur = centre_couleur.get(str(j), "#888888")
            folium.PolyLine(
                locations=[
                    [float(m_coord["latitude"]), float(m_coord["longitude"])],
                    [float(c_coord["latitude"]), float(c_coord["longitude"])],
                ],
                color=couleur, weight=1.5, opacity=0.6,
            ).add_to(m)
        except KeyError:
            pass

    # Légende
    items = "".join([
        f'<div><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:{palette[idx % len(palette)]};margin-right:6px;"></span>Centre {j}</div>'
        for idx, j in enumerate(centres_ouverts_vals)
    ])
    legend = f"""
    <div style="position:fixed;bottom:30px;right:30px;z-index:1000;
                background:white;padding:12px 16px;border:1px solid #ddd;
                border-radius:8px;font-size:12px;box-shadow:2px 2px 6px rgba(0,0,0,0.15);">
      <b style="display:block;margin-bottom:6px;">Légende</b>
      <div>🔵 Ménage</div>
      <div>🟢 Centre ouvert</div>
      <div>🔴 Centre fermé</div>
      <hr style="margin:6px 0">
      {items}
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))
    return m._repr_html_()


def kpi_card(value, label, css_class, icon):
    return f"""
    <div class="kpi-card {css_class}">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <p class="kpi-value">{value}</p>
                <p class="kpi-label">{label}</p>
            </div>
            <div style="font-size:2.5rem;opacity:0.3;">{icon}</div>
        </div>
    </div>
    """


# ══════════════════════════════════════════════════════════════════════════════
# PAGE : Données
# ══════════════════════════════════════════════════════════════════════════════
if page == "📂 Données":
    st.markdown("## 📂 Chargement des données")
    uploaded_file = st.file_uploader("Charger un fichier CSV de ménages", type="csv")
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
        if "id" not in df.columns:
            df["id"] = range(len(df))
        if "poids_dechets" not in df.columns:
            df["poids_dechets"] = 1.0
            st.info("Colonne 'poids_dechets' absente — valeur par défaut 1.0 appliquée.")
        st.session_state["df"] = df
        st.success(f"✅ {len(df)} ménages chargés")
        st.dataframe(df.head(10), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE : Clustering
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔹 Clustering":
    st.markdown("## 🔹 Clustering des ménages")
    if "df" not in st.session_state:
        st.warning("Veuillez d'abord charger des données.")
    else:
        k = st.slider("Nombre de clusters", min_value=2, max_value=10, value=3)
        if st.button("🚀 Lancer le clustering"):
            with st.spinner("Clustering en cours..."):
                df, centres = clustering_menage(st.session_state["df"], k)
                sauvegarde_resultats(df, centres)
                st.session_state["df_cluster"] = df
                st.session_state["centres"] = centres
            st.success(f"✅ {k} clusters créés")

        if "df_cluster" in st.session_state:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.map(st.session_state["df_cluster"][["latitude", "longitude"]])
            with col2:
                st.markdown("**Centres candidats**")
                st.dataframe(st.session_state["centres"], use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE : Optimisation
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⚡ Optimisation":
    st.markdown("## ⚡ Optimisation LRP")
    if "df_cluster" not in st.session_state:
        st.warning("Veuillez d'abord effectuer le clustering.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            nb_vehicules = st.number_input("Véhicules", min_value=1, max_value=10, value=2)
        with col2:
            Q = st.number_input("Capacité centre (Q)", min_value=1, value=20)
        with col3:
            Nmax = st.number_input("Max centres ouverts", min_value=1, value=3)
        with col4:
            Dmax = st.number_input("Distance max (m)", min_value=100, value=2000)

        if st.button("🚀 Lancer l'optimisation"):
            with st.spinner("Construction du graphe routier..."):
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
            with st.spinner("Résolution PySCIPOpt..."):
                try:
                    model, meta = construire_modele(
                        menages_path="data/processed/menages_cluster.csv",
                        centres_path="data/processed/centres.csv",
                        dist_path="data/processed/distances.csv",
                        nb_vehicules=int(nb_vehicules),
                        Q=int(Q), Nmax=int(Nmax), Dmax=int(Dmax),
                    )
                    solution = resoudre_modele(model, meta)
                    st.session_state["solution"] = solution
                    st.session_state.pop("carte_html", None)
                    st.success("✅ Optimisation terminée — consultez l'onglet Résultats")
                except RuntimeError as e:
                    st.error(f"Erreur solveur : {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE : Résultats
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Résultats":
    st.markdown("## 📊 Résultats de l'optimisation")
    if "solution" not in st.session_state:
        st.warning("Veuillez d'abord lancer l'optimisation.")
    else:
        solution = st.session_state["solution"]
        menages = st.session_state["df_cluster"]
        centres = st.session_state["centres"].copy()

        # ── KPI ──────────────────────────────────────────────────────────────
        dist_km = round(solution["cout_total"] / 1000, 3)
        nb_centres = len(solution["centres"])
        nb_vehicules = nb_centres  # 1 véhicule par centre ouvert
        nb_menages = len(menages)
        nb_affectes = len(set(i for i, j in solution["affectations"]))
        taux = f"{round(nb_affectes / nb_menages * 100)}%"

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(kpi_card(f"{dist_km} km", "Distance totale", "kpi-blue", "🗺️"), unsafe_allow_html=True)
        with c2:
            st.markdown(kpi_card(nb_centres, "Points ouverts", "kpi-orange", "📍"), unsafe_allow_html=True)
        with c3:
            st.markdown(kpi_card(nb_vehicules, "Véhicules utilisés", "kpi-green", "🚛"), unsafe_allow_html=True)
        with c4:
            st.markdown(kpi_card(taux, "Ménages couverts", "kpi-purple", "🏠"), unsafe_allow_html=True)

        st.markdown("---")

        # ── Carte + Tableau ───────────────────────────────────────────────────
        col_map, col_table = st.columns([3, 2])

        with col_map:
            st.markdown('<div class="section-title">Carte des tournées</div>', unsafe_allow_html=True)
            if "carte_html" not in st.session_state:
                with st.spinner("Génération de la carte..."):
                    st.session_state["carte_html"] = construire_carte(
                        menages, centres, solution
                    )
            components.html(st.session_state["carte_html"], height=480, scrolling=False)

        with col_table:
            st.markdown('<div class="section-title">Détail des affectations</div>', unsafe_allow_html=True)

            # Construire le tableau des affectations avec distances
            try:
                dist_matrix = pd.read_csv("data/processed/distances.csv", index_col=0)
                dist_matrix.index = dist_matrix.index.astype(str)
                dist_matrix.columns = dist_matrix.columns.astype(str)

                rows = []
                for idx, (i, j) in enumerate(solution["affectations"]):
                    try:
                        val = dist_matrix.at[str(i), str(j)]
                        if hasattr(val, "iloc"):
                            val = val.iloc[0]
                        d_km = round(float(val) / 1000, 3)
                    except Exception:
                        d_km = "-"
                    rows.append({"Ménage": i, "Centre": j, "Distance (km)": d_km})

                df_aff = pd.DataFrame(rows)
                st.dataframe(df_aff, use_container_width=True, height=380)

                # Export CSV
                csv = df_aff.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Exporter les résultats (CSV)",
                    data=csv,
                    file_name="affectations.csv",
                    mime="text/csv",
                )
            except Exception as e:
                st.warning(f"Tableau non disponible : {e}")