import os

import pandas as pd
import requests
import streamlit as st


API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Movie Cloud Recommender", layout="wide")
st.title("Movie Cloud Recommender")
st.caption("Interactive recommendation demo with sampled evaluation metrics.")


def get_json(path: str):
    response = requests.get(f"{API_URL}{path}", timeout=60)
    response.raise_for_status()
    return response.json()


def post_json(path: str, payload: dict):
    response = requests.post(f"{API_URL}{path}", json=payload, timeout=60)
    response.raise_for_status()
    return response.json()


def load_movies(query: str = "") -> list[dict]:
    path = f"/movies/search?q={query}&limit=100" if query else "/movies?limit=100"
    return get_json(path)


with st.sidebar:
    st.header("Add Movie")
    new_title = st.text_input("Title")
    new_genres = st.text_input("Genres", placeholder="Action|Drama")
    new_rating = st.number_input("Initial rating", min_value=0.5, max_value=5.0, value=3.0, step=0.5)
    if st.button("Add movie"):
        if not new_title.strip():
            st.warning("Title is required.")
        else:
            try:
                created = post_json(
                    "/movies",
                    {"title": new_title.strip(), "genres": new_genres.strip(), "user_rating": float(new_rating)},
                )
                st.success(f"Added: {created['title']} ({created['movie_id']})")
            except Exception as exc:
                st.error(str(exc))


demo_tab, evaluation_tab, advanced_tab = st.tabs(["Demo", "Evaluation", "Advanced"])

with demo_tab:
    st.subheader("Movie-to-movie recommendation")
    search_query = st.text_input("Search movie title", value="Toy Story")
    try:
        movies = load_movies(search_query.strip())
    except Exception as exc:
        st.error(f"Could not load movies: {exc}")
        movies = []

    movie_options = {f"{movie['title']}  [{movie['movie_id']}]": movie for movie in movies}
    selected_label = st.selectbox("Select a movie", options=list(movie_options.keys()), index=0 if movie_options else None)
    limit = st.slider("Recommendations", min_value=4, max_value=20, value=4, step=1)
    selected_movie = movie_options.get(selected_label) if selected_label else None

    if st.button("Get similar movies", type="primary", disabled=selected_movie is None):
        try:
            data = get_json(f"/recommend/movie?movie_id={selected_movie['movie_id']}&limit={limit}")
            rows = data.get("recommendations", [])
            st.caption(f"model={data['model']} cached={data['cached']}")
            if not rows:
                st.warning("No recommendations found.")
            else:
                for item in rows:
                    with st.container(border=True):
                        cols = st.columns([4, 2, 1, 1])
                        cols[0].markdown(f"**{item['title']}**")
                        cols[0].caption(item.get("genres") or "")
                        cols[1].write("Similar rating behavior")
                        cols[1].caption(item.get("reason") or "")
                        cols[2].metric("Score", f"{item.get('score') or 0:.3f}", help="Sampled rating-vector cosine similarity.")
                        stats = get_json(f"/clicks/{item['movie_id']}")
                        cols[3].metric("Demo CTR", f"{stats['click_percentage']:.1f}%", help="Local demo click-through rate from recommendation impressions and clicks.")
                        if cols[3].button("Click", key=f"click-{item['movie_id']}"):
                            post_json("/clicks", {"movie_id": int(item["movie_id"])})
                            st.rerun()
        except Exception as exc:
            st.error(str(exc))

with evaluation_tab:
    st.subheader("Sampled offline evaluation")
    st.caption("This runs a lightweight leave-one-out evaluation against the current database and movie-cosine recommender.")
    cols = st.columns(2)
    sample_size = cols[0].slider("Sample users", min_value=5, max_value=100, value=20, step=5)
    top_k = cols[1].slider("Top-K", min_value=5, max_value=50, value=10, step=5)

    if st.button("Run evaluation", type="primary"):
        try:
            result = get_json(f"/evaluation/summary?sample_size={sample_size}&k={top_k}")
            metric_cols = st.columns(6)
            metric_cols[0].metric(f"Precision@{top_k}", f"{result['precision_at_k']:.4f}")
            metric_cols[1].metric(f"Recall@{top_k}", f"{result['recall_at_k']:.4f}")
            metric_cols[2].metric(f"NDCG@{top_k}", f"{result['ndcg_at_k']:.4f}")
            metric_cols[3].metric(f"HitRate@{top_k}", f"{result['hitrate_at_k']:.4f}")
            metric_cols[4].metric("Avg Latency", f"{result['avg_latency_ms']:.1f} ms")
            metric_cols[5].metric("p95 Latency", f"{result['p95_latency_ms']:.1f} ms")

            st.write("Dataset")
            st.json(result["dataset"])
            st.caption(result["note"])
            st.dataframe(pd.DataFrame(result["cases"]), use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(str(exc))

    with st.expander("Cold-start interpretation"):
        st.write(
            "A newly added movie such as 战狼 is not part of the original MovieLens 1M catalog. "
            "In this demo it should be interpreted as a cold-start item with title, genres, and an optional initial rating. "
            "When rating history is missing, genre/title metadata is only a fallback; rating-behavior similarity remains the main demo path for existing movies."
        )

with advanced_tab:
    st.subheader("Advanced recommendation mode")
    st.caption("Second-stage APIs for ALS/BPR/Hybrid experiments. Not used for original-repo parity.")
    user_id = st.number_input("User ID", min_value=1, value=1, step=1)
    seed_movie_id = st.number_input("Seed Movie ID", min_value=1, value=1, step=1)
    mode = st.radio("Mode", ["Hybrid", "User CF", "Popular", "Similar"], horizontal=True)
    path_map = {
        "Hybrid": f"/recommend/hybrid/{user_id}?seed_movie_id={seed_movie_id}&limit=10",
        "User CF": f"/recommend/user/{user_id}?limit=10",
        "Popular": "/recommend/popular?limit=10",
        "Similar": f"/recommend/similar/{seed_movie_id}?limit=10",
    }
    if st.button("Run advanced recommendation"):
        try:
            data = get_json(path_map[mode])
            st.caption(f"request={path_map[mode]} cached={data['cached']}")
            st.dataframe(pd.DataFrame(data.get("recommendations", [])), use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(str(exc))

with st.expander("System metrics"):
    try:
        st.json({"cache": get_json("/metrics/cache"), "system": get_json("/metrics/system")})
    except Exception as exc:
        st.warning(str(exc))
