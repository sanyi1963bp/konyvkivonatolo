#!/usr/bin/env python3
"""
nCore E-book Scraper CLI
========================
Parancssori interfész az nCore e-book gyűjtéséhez

Használat:
    python main.py              # Interaktív menü
    python main.py update       # Új könyvek letöltése
    python main.py history 500  # Régi könyvek az 500. oldaltól
    python main.py search       # Keresés az adatbázisban
    python main.py download 123 # Letöltés ID alapján
    python main.py stats        # Statisztikák
"""

import argparse
import sys

from config import load_config, is_configured, setup_wizard, ensure_directories
from database import init_database, search_books, get_statistics, count_books, get_formats
from scraper import Scraper
from downloader import Downloader


def cmd_update(args):
    """Új könyvek scrape-elése."""
    print("\n🔄 Frissítés - új könyvek keresése...\n")
    
    scraper = Scraper()
    try:
        count = scraper.scrape_update()
        print(f"\n✅ Kész! {count} új könyv mentve.")
    except KeyboardInterrupt:
        scraper.stop()
        print("\n⛔ Megszakítva.")


def cmd_history(args):
    """Régi könyvek scrape-elése."""
    page = args.page or 1
    print(f"\n📜 Régi könyvek keresése ({page}. oldaltól)...\n")
    
    scraper = Scraper()
    try:
        count = scraper.scrape_history(start_page=page)
        print(f"\n✅ Kész! {count} könyv mentve.")
    except KeyboardInterrupt:
        scraper.stop()
        print("\n⛔ Megszakítva.")


def cmd_fullscan(args):
    """Teljes scrape: új + régi könyvek."""
    max_pages = args.max_pages or 3000
    print(f"\n🚀 Teljes scan indítása (max {max_pages} oldal a history fázisban)...\n")
    
    scraper = Scraper()
    try:
        count = scraper.scrape_full(max_pages=max_pages)
        print(f"\n✅ Kész! Összesen {count} könyv mentve.")
    except KeyboardInterrupt:
        scraper.stop()
        print("\n⛔ Megszakítva.")


def cmd_search(args):
    """Keresés az adatbázisban."""
    query = args.query or ""
    
    if not query:
        query = input("\n🔍 Keresés: ").strip()
    
    if not query:
        print("Üres keresés.")
        return
    
    books = search_books(query=query, limit=20)
    
    if not books:
        print(f"\n❌ Nincs találat: '{query}'")
        return
    
    print(f"\n📚 Találatok ({len(books)} db):\n")
    print("-" * 80)
    
    for book in books:
        print(f"  [{book['id']:>4}] {book['szerzo'][:20]:<20} - {book['cim'][:40]}")
    
    print("-" * 80)
    print("\nLetöltéshez: python main.py download <ID>")


def cmd_download(args):
    """Torrent letöltése."""
    if not args.ids:
        print("❌ Add meg a letöltendő könyv ID-ját!")
        print("   Példa: python main.py download 123 456 789")
        return
    
    ids = [int(i) for i in args.ids]
    
    print(f"\n📥 {len(ids)} torrent letöltése...\n")
    
    downloader = Downloader()
    if not downloader.connect():
        return
    
    for book_id in ids:
        downloader.download_by_id(book_id)


def cmd_stats(args):
    """Adatbázis statisztikák."""
    stats = get_statistics()
    
    print("\n" + "=" * 50)
    print("📊 Adatbázis Statisztikák")
    print("=" * 50)
    
    print(f"\n  Összes könyv: {stats['total']:,}".replace(",", " "))
    print(f"  Legrégebbi:   {stats['oldest'] or 'N/A'}")
    print(f"  Legújabb:     {stats['newest'] or 'N/A'}")
    
    if stats['formats']:
        print("\n  Formátumok:")
        for fmt, cnt in stats['formats'].items():
            print(f"    {fmt:<10} {cnt:>6} db")
    
    print()


def interactive_menu():
    """Interaktív menü."""
    while True:
        print("\n" + "=" * 50)
        print("📚 nCore E-book Scraper")
        print("=" * 50)
        
        stats = get_statistics()
        print(f"   Adatbázis: {stats['total']:,} könyv".replace(",", " "))
        
        print("\n  1. 🔄 Frissítés (új könyvek)")
        print("  2. 📜 Régi könyvek keresése")
        print("  3. 🚀 Teljes scan (új + régi)")
        print("  4. 🔍 Keresés az adatbázisban")
        print("  5. 📥 Letöltés ID alapján")
        print("  6. 📊 Statisztikák")
        print("  7. ⚙️  Beállítások")
        print("  0. 🚪 Kilépés")
        
        choice = input("\nVálasztás: ").strip()
        
        if choice == "1":
            cmd_update(argparse.Namespace())
            
        elif choice == "2":
            page_str = input("Kezdő oldal [1]: ").strip()
            page = int(page_str) if page_str.isdigit() else 1
            cmd_history(argparse.Namespace(page=page))
            
        elif choice == "3":
            max_str = input("Max oldalak a history fázisban [3000]: ").strip()
            max_pages = int(max_str) if max_str.isdigit() else 3000
            cmd_fullscan(argparse.Namespace(max_pages=max_pages))
            
        elif choice == "4":
            cmd_search(argparse.Namespace(query=None))
            
        elif choice == "5":
            ids_str = input("Könyv ID(k), szóközzel elválasztva: ").strip()
            if ids_str:
                ids = [i for i in ids_str.split() if i.isdigit()]
                cmd_download(argparse.Namespace(ids=ids))
            
        elif choice == "6":
            cmd_stats(argparse.Namespace())
            
        elif choice == "7":
            setup_wizard()
            
        elif choice == "0":
            print("\n👋 Viszlát!\n")
            break
        
        else:
            print("❌ Érvénytelen választás!")


def main():
    """Belépési pont."""
    parser = argparse.ArgumentParser(
        description="nCore E-book Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Példák:
  python main.py                  Interaktív menü
  python main.py update           Új könyvek letöltése
  python main.py history 500      Régi könyvek az 500. oldaltól
  python main.py fullscan         Teljes scan (új + régi)
  python main.py search "Asimov"  Keresés
  python main.py download 123     Letöltés ID alapján
  python main.py stats            Statisztikák
        """
    )
    
    subparsers = parser.add_subparsers(dest="command")
    
    # update
    subparsers.add_parser("update", help="Új könyvek scrape-elése")
    
    # history
    history_parser = subparsers.add_parser("history", help="Régi könyvek scrape-elése")
    history_parser.add_argument("page", type=int, nargs="?", default=1, help="Kezdő oldal")
    
    # fullscan (ÚJ!)
    fullscan_parser = subparsers.add_parser("fullscan", help="Teljes scan: új + régi könyvek")
    fullscan_parser.add_argument("--max-pages", type=int, default=3000, help="Max oldalak a history fázisban (alapért.: 3000)")
    
    # search
    search_parser = subparsers.add_parser("search", help="Keresés az adatbázisban")
    search_parser.add_argument("query", nargs="?", help="Keresési kifejezés")
    
    # download
    download_parser = subparsers.add_parser("download", help="Torrent letöltése")
    download_parser.add_argument("ids", nargs="*", help="Könyv ID-k")
    
    # stats
    subparsers.add_parser("stats", help="Adatbázis statisztikák")
    
    args = parser.parse_args()
    
    # Inicializálás
    ensure_directories()
    init_database()
    
    # Konfiguráció ellenőrzés
    if not is_configured() and args.command in ["update", "history", "download"]:
        print("⚠️  Első indítás - konfiguráció szükséges!")
        setup_wizard()
    
    # Parancs végrehajtása
    if args.command == "update":
        cmd_update(args)
    elif args.command == "history":
        cmd_history(args)
    elif args.command == "fullscan":
        cmd_fullscan(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "download":
        cmd_download(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        # Nincs parancs -> interaktív menü
        if not is_configured():
            setup_wizard()
        interactive_menu()


if __name__ == "__main__":
    main()
