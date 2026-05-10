from app.database import init_db
from scripts.admin.load_target_inventory import apply_catalog_titles_and_descriptions


def main() -> None:
    init_db()
    apply_catalog_titles_and_descriptions()


if __name__ == "__main__":
    main()
