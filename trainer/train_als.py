import time

from implicit.als import AlternatingLeastSquares

from train_common import MODEL_DIR, load_interactions, save_bundle


def main() -> None:
    started = time.time()
    user_items, user_to_index, _movie_to_index, index_to_movie = load_interactions()
    model = AlternatingLeastSquares(factors=64, regularization=0.05, iterations=20)
    model.fit(user_items.T.tocsr())
    save_bundle(MODEL_DIR / "implicit_als.joblib", model, user_items, user_to_index, index_to_movie)
    print(f"train_time_seconds={time.time() - started:.3f}")


if __name__ == "__main__":
    main()
