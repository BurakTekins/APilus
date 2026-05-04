from django.core.management.base import BaseCommand

from APilus.index import build_index, _index_fingerprint, _resolve_paths


class Command(BaseCommand):
    help = "Build the FAISS RAG index from corpus JSON files"

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-if-fresh',
            action='store_true',
            help='Skip rebuild if existing index fingerprint matches current corpus and config.',
        )

    def handle(self, *args, **options):
        if options['skip_if_fresh']:
            try:
                _BASE_DIR, INDEX_PATH, json_files = _resolve_paths()
                VERSION_FILE = INDEX_PATH / "version.txt"
                expected_fingerprint = _index_fingerprint(json_files)

                on_disk_fingerprint = ""
                if VERSION_FILE.exists():
                    try:
                        on_disk_fingerprint = VERSION_FILE.read_text(encoding="utf-8").strip()
                    except OSError:
                        on_disk_fingerprint = ""

                if on_disk_fingerprint == expected_fingerprint:
                    self.stdout.write("RAG index is fresh, skipping rebuild.")
                    return
            except Exception as exc:
                self.stdout.write(
                    self.style.WARNING(f"Freshness check failed ({exc}), proceeding with build.")
                )

        self.stdout.write("Starting RAG index build...")
        try:
            build_index()
        except Exception as exc:
            raise SystemExit(f"Index build failed: {exc}") from exc
        self.stdout.write(self.style.SUCCESS("RAG index built successfully."))
