from flask import Flask, render_template, request, redirect, jsonify
from flask_compress import Compress
import sqlite3
import webbrowser
import socket
from collections import defaultdict, Counter
import logging
import stock_app_proposed_order_data_fetcher
import logging
import requests
from urllib.parse import quote
import threading
from math import ceil
import os
import re
from waitress import serve
import stock_app_magento_sync

db = r'product_inventory.db'
log = r'logs/stock_app.log'
stock_app_port = 8080
ALLOWED_TABLES = {'growkits', 'spores', 'cannabis_seeds', 'misc', 'cultures'}


manufacturer_routes = {
    'Royal Queen Seeds': 'rqs',
    'Fastbuds': 'fastbuds',
    'Green House Seed Co': 'ghs',
    'Barneys Farm': 'barney',
    'Dutch Passion': 'dutch_passion'
}
#Logging
logging.basicConfig(filename=log, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
flask_logger = logging.getLogger('werkzeug')
flask_logger.handlers.clear()  # Remove any existing handlers
console_handler = logging.StreamHandler()  # Log to console (stdout)
console_handler.setLevel(logging.ERROR)
flask_logger.addHandler(console_handler)
flask_logger.setLevel(logging.ERROR)
logging.getLogger('waitress').setLevel(logging.ERROR)


app = Flask(__name__)
Compress(app)


def get_db_connection():
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def inventory():
    growkits_grouped, spores_grouped, misc_grouped, cultures_grouped = get_mushrooms_grouped()
    # Collect all manufacturers from all product groups
    all_manufacturers = set()
    for group in [growkits_grouped, spores_grouped, misc_grouped, cultures_grouped]:
        if isinstance(group, dict):
            for k, v in group.items():
                if isinstance(v, dict):
                    for name, products in v.items():
                        for product in products:
                            if 'manufacturer' in product:
                                all_manufacturers.add(product['manufacturer'])
                elif isinstance(v, list):
                    for product in v:
                        if isinstance(product, dict) and 'manufacturer' in product:
                            all_manufacturers.add(product['manufacturer'])
                elif isinstance(v, str):
                    continue
        elif isinstance(group, list):
            for product in group:
                if isinstance(product, dict) and 'manufacturer' in product:
                    all_manufacturers.add(product['manufacturer'])
    all_manufacturers.discard('None')
    all_manufacturers = sorted(m for m in all_manufacturers if m)
    # SSR initial state from query params
    active_tab = request.args.get('tab', 'all')
    # Only allow known tabs
    allowed_tabs = {'all', 'growkits', 'spores', 'swabs', 'cultures', 'misc'}
    if active_tab not in allowed_tabs:
        active_tab = 'all'

    initial_manufacturer = request.args.get('manufacturer') or ''

    return render_template('inventory.html',
                           products_grouped=growkits_grouped,
                           route='',
                           spores_grouped=spores_grouped,
                           misc_grouped=misc_grouped,
                           cultures_grouped=cultures_grouped,
                           all_manufacturers=all_manufacturers,
                           active_tab=active_tab,
                           initial_manufacturer=initial_manufacturer)

@app.route('/proposed_order')
def proposed_order():
    proposal_data = get_grow_kit_order_proposal()
    all_manufacturers = get_distinct_manufacturers()
    return render_template('proposed_order.html',
                           route='proposed_order',
                           current_manufacturer='Fresh Mushrooms',
                           all_manufacturers=sorted(all_manufacturers),
                           **proposal_data)

@app.route('/fastbuds')
def fastbuds():
    on_sale = request.args.get('on_sale') == '1'
    seeds_grouped, pack_sizes = get_seeds_grouped('Fastbuds', on_sale=on_sale)
    return render_template('seed_inventory.html',
                           seeds_grouped=seeds_grouped,
                           pack_sizes=pack_sizes,
                           page_title='Fastbuds',
                           route='fastbuds',
                           page_header='420FB' + (' - On Sale' if on_sale else ''),
                           on_sale=on_sale,
                           active_tab=request.args.get('tab', 'all'))

@app.route('/ghs')
def green_house():
    on_sale = request.args.get('on_sale') == '1'
    seeds_grouped, pack_sizes = get_seeds_grouped('Green House Seed Co', on_sale=on_sale)
    return render_template('seed_inventory.html', 
                           seeds_grouped=seeds_grouped, 
                           pack_sizes=pack_sizes, 
                           page_title='Green House Seed Co', 
                           route='ghs', 
                           page_header='GHS' + (' - On Sale' if on_sale else ''),
                           on_sale=on_sale,
                           show_toggle=True,
                           active_tab=request.args.get('tab', 'all'))

@app.route('/ghs/all')
def green_house_all():
    on_sale = request.args.get('on_sale') == '1'
    seeds_grouped, pack_sizes = get_seeds('Green House Seed Co', on_sale=on_sale)
    return render_template('single_table_seed_inventory.html', 
                           seeds_grouped=seeds_grouped, 
                           pack_sizes=pack_sizes, 
                           page_title='Green House Seed Co', 
                           route='ghs/all', 
                           page_header='GHS' + (' - On Sale' if on_sale else ''),
                           on_sale=on_sale,
                           show_toggle=True)
@app.route('/barney')
def barney():
    on_sale = request.args.get('on_sale') == '1'
    seeds_grouped, pack_sizes = get_seeds_grouped('Barneys Farm', on_sale=on_sale)
    return render_template('seed_inventory.html',
                           seeds_grouped=seeds_grouped, pack_sizes=pack_sizes,
                           page_title='Barneys Farm',
                           route='barney',
                           page_header='Barney' + (' - On Sale' if on_sale else ''),
                           on_sale=on_sale,
                           active_tab=request.args.get('tab', 'all'))

@app.route('/dutch_passion')
def dutch_passion():
    on_sale = request.args.get('on_sale') == '1'
    seeds_grouped, pack_sizes = get_seeds_grouped('Dutch Passion', on_sale=on_sale)
    return render_template('seed_inventory.html',
                           seeds_grouped=seeds_grouped,
                           pack_sizes=pack_sizes,
                           page_title='Dutch Passion',
                           route='dutch_passion',
                           page_header='DP' + (' - On Sale' if on_sale else ''),
                           on_sale=on_sale,
                           active_tab=request.args.get('tab', 'all'))

@app.route('/rqs')
def rqs():
    on_sale = request.args.get('on_sale') == '1'
    seeds_grouped, pack_sizes = get_seeds_grouped('Royal Queen Seeds', on_sale=on_sale)
    return render_template('seed_inventory.html',
                           seeds_grouped=seeds_grouped,
                           pack_sizes=pack_sizes,
                           page_title='Royal Queen Seeds',
                           route='rqs',
                           page_header='RQS' + (' - On Sale' if on_sale else ''),
                           on_sale=on_sale,
                           active_tab=request.args.get('tab', 'all'))

@app.route('/all_seeds')
def all_seeds():
    on_sale = request.args.get('on_sale') == '1'
    with get_db_connection() as conn:
        if on_sale:
            cursor = conn.execute("SELECT * FROM cannabis_seeds WHERE special_price IS NOT NULL ORDER BY manufacturer, storage_location_number;")
        else:
            cursor = conn.execute("SELECT * FROM cannabis_seeds ORDER BY manufacturer, storage_location_number;")
        seeds = cursor.fetchall()
        allowed_fields = get_allowed_fields(conn, 'cannabis_seeds')
    seeds_by_type = defaultdict(lambda: defaultdict(list))
    pack_sizes = defaultdict(set)
    all_manufacturers = set()
    for seed in seeds:
        seed_type = seed['seed_type']
        name = seed['name']
        manufacturer = seed['manufacturer']
        pack_size = seed['pack_size']
        seeds_by_type[seed_type][(name, manufacturer)].append(seed)
        pack_sizes[seed_type].add(pack_size)
        if manufacturer:
            all_manufacturers.add(manufacturer)
    all_manufacturers = sorted(all_manufacturers)
    return render_template('all_seeds_inventory.html',
                           seeds_by_type=seeds_by_type,
                           route='all_seeds',
                           pack_sizes=pack_sizes,
                           allowed_fields=allowed_fields,
                           all_manufacturers=all_manufacturers,
                           on_sale=on_sale,
                           active_tab=request.args.get('tab', 'all'),
                           initial_manufacturer=request.args.get('manufacturer') or '')

query_table = {
    'cannabis_seeds': ['name', 'pack_size', 'seed_type', 'manufacturer', 'stock', 'retail_price', 'special_price', 'sync_special_price_to_magento', 'storage_location_number'],
    'spores'        : ['name', 'form', 'stock', 'retail_price', 'special_price', 'sync_special_price_to_magento'],
    'growkits'      : ['name', 'size', 'manufacturer', 'stock', 'retail_price', 'special_price', 'sync_special_price_to_magento'],
    'misc'          : ['name',  'stock', 'retail_price', 'special_price', 'sync_special_price_to_magento'],
    'cultures'      : ['name', 'form', 'stock', 'retail_price', 'special_price', 'sync_special_price_to_magento']
}

@app.route('/update_stock/<table>/<int:id>', methods=["POST"])
def update_stock(table, id):
    if table not in ALLOWED_TABLES:
        print(f'not allowed: table: {str(table)}')
        return "Invalid table specified.", 400
    last_refresh_stock = int(request.form['last_refresh_stock'])
    submitted_stock = int(request.form['submitted_stock']) if 'submitted_stock' in request.form and request.form['submitted_stock'] else last_refresh_stock
    stock_difference = submitted_stock - last_refresh_stock

    # Optional: get order_number and sku from request (for logging)
    order_number = request.form.get('order_number')
    sku = request.form.get('sku')

    # sync stock with magento
    if (last_refresh_stock <= 0 and submitted_stock > 0) or (last_refresh_stock > 0 and submitted_stock == 0):
        async_sync_stock_with_magento(table, id, submitted_stock)
    if not stock_difference:
        return redirect(request.headers.get('Referer', '/'))
    log = f'{"-"*10}\nid: {id}, table: {table}, last_refresh_stock: {last_refresh_stock}, submitted_stock: {submitted_stock}, stock_difference: {stock_difference}'
    with get_db_connection() as conn:
        query = 'UPDATE {} SET stock = stock + ? WHERE id = ?'.format(table)
        conn.execute(query, (stock_difference, id))
        conn.commit()
        # Ensure we select manufacturer/manufacturer_id when available so it gets logged
        pragma_rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing_cols = [r[1] for r in pragma_rows]
        to_select_cols = list(query_table[table])
        # Exclude only sync flag from logs; keep special_price for formatting
        if 'sync_special_price_to_magento' in to_select_cols:
            to_select_cols.remove('sync_special_price_to_magento')
        if 'manufacturer' in existing_cols and 'manufacturer' not in to_select_cols:
            to_select_cols.append('manufacturer')


        to_select = ', '.join(to_select_cols)
        query = f'SELECT {to_select} FROM {table} WHERE id = ?'
        cursor = conn.execute(query, (id,))
        product = cursor.fetchone()
        # Enhanced logging: include order_number and sku if present
        extra = ""
        if order_number:
            extra += f"Order #{order_number} "
        if sku:
            extra += f"SKU: {sku} "
        # Log all selected columns (including manufacturer/manufacturer_id when available)

        def _fmt_pct(discount: float) -> str:
            """Round to nearest 1% using half-up semantics and return as string."""
            try:
                d = float(discount)
                # Half-up rounding for positives/negatives
                if d >= 0:
                    return str(int(d + 0.5))
                else:
                    return str(int(d - 0.5))
            except Exception:
                # Fallback to integer formatting
                try:
                    return f"{int(round(discount))}"
                except Exception:
                    return "0"

        def format_part(col_name):
            if col_name == 'retail_price':
                retail_val = product['retail_price']
                # Use special_price if present to show old -> new
                special_val = None
                # product can be sqlite3.Row or tuple; handle both
                try:
                    special_val = product['special_price'] if 'special_price' in product.keys() else None
                except Exception:
                    # tuple fallback handled below where we skip keys check
                    pass
                if special_val is None:
                    # Try tuple-style access
                    try:
                        # Map columns to values
                        col_map = {c: v for c, v in zip(to_select_cols, product)}
                        special_val = col_map.get('special_price')
                    except Exception:
                        special_val = None
                # If special price has a meaningful value, log as "retail -> special (X%)"
                try:
                    if special_val is not None and str(special_val) != '' and float(special_val) > 0:
                        # Try to append discount percent
                        try:
                            rv = float(retail_val)
                            sv = float(special_val)
                            if rv > 0:
                                disc = (rv - sv) / rv * 100.0
                                return f"{col_name}: {retail_val} -> {special_val} ({_fmt_pct(disc)}%)"
                        except Exception:
                            pass
                        return f"{col_name}: {retail_val} -> {special_val}"
                except Exception:
                    # If not a number, fall back to plain retail
                    pass
                return f"{col_name}: {retail_val}"
            elif col_name == 'special_price':
                # Do not log special_price separately (it is shown with retail_price)
                return None
            else:
                return f"{col_name}: {product[col_name]}"
        parts = []
        for col in to_select_cols:
            part = format_part(col)
            if part is not None:
                parts.append(part)
        logged_parts = parts

        logging.info(extra + log + '\n' + ', '.join(logged_parts))
    return redirect(request.headers.get('Referer', '/'))

@app.route('/refresh', methods=["POST"])
def refresh_page():
    return redirect(request.headers.get('Referer', '/'))

@app.route('/choose_table', methods=["GET", "POST"])
def choose_table():
    if request.method == "POST":
        selected_table = request.form.get("table")
        if selected_table not in ALLOWED_TABLES:
            return "Invalid table selected.", 400
        return redirect(f"/add_product/{selected_table}")
    return render_template("choose_table.html", tables=sorted(ALLOWED_TABLES))

@app.route('/test', methods=["GET"])
def test():
    webbrowser.open('https://www.kosmickitchen.eu/cannabis-seeds/auto-kerosene-krash-dutch-passion.html', new=2)
    return 'https://www.kosmickitchen.eu/cannabis-seeds/auto-kerosene-krash-dutch-passion.html' #redirect(request.headers.get('Referer', '/'))

@app.route('/add_product/<table>', methods=["GET", "POST"])
def add_product(table):
    with get_db_connection() as conn:
        allowed_fields = get_allowed_fields(conn, table)
        unique_values = get_unique_values(table)

        # Determine which column in this table acts as the "variant attribute"
        variant_attr = None
        if table == 'cannabis_seeds':
            variant_attr = 'pack_size'
        elif table == 'spores':
            variant_attr = 'form'
        elif table == 'growkits':
            variant_attr = 'size'

        # Exclude variant-only fields from "base_fields"
        excluded_variant_fields = {
            'manufacturer_id', 'wholesale_price',
            'retail_price', 'desired_stock', 'stock', 'magento_sku',
            'special_price', 'sync_special_price_to_magento'
        }
        base_fields = [f for f in allowed_fields if f not in excluded_variant_fields and f != variant_attr]

        if request.method == 'POST':
            logging.info(f"Received POST to add_product for table: {table}")
            logging.info(f"base_fields: {base_fields}")

            # Gather base data
            base_data = {}
            for field in base_fields:
                val = request.form.get(field, "").strip()
                # If the field is parent_sku and empty, store None (NULL in SQLite)
                if field == "parent_sku" and not val:
                    base_data[field] = None
                elif val:
                    base_data[field] = val

            logging.info(f"base_data: {base_data}")

            if not base_data:
                logging.info("base_data is empty -> returning 400")
                return "All fields are required.", 400

            # --- Validate numeric fields in base_data ---
            for field in base_data:
                if field in ["retail_price", "storage_location_number", "wholesale_price"]:
                    try:
                        float(base_data[field])
                    except ValueError:
                        return f"{field} must be numeric.", 400
                if field in ["stock", "desired_stock"]:
                    try:
                        int(base_data[field])
                    except ValueError:
                        return f"{field} must be an integer.", 400
                if field == "size":
                    try:
                        int(base_data[field])
                    except ValueError:
                        return "size must be an integer.", 400

            # Remove the variant_attr from base_data if it got included
            if variant_attr and variant_attr in base_data:
                del base_data[variant_attr]

            # Now gather variant-related lists
            variants = request.form.getlist('variant_attr[]') if variant_attr else [None]
            variant_manufacturer_ids = request.form.getlist('variant_manufacturer_id[]')
            variant_wholesale_prices = request.form.getlist('variant_wholesale_price[]')
            prices = request.form.getlist('variant_retail_price[]')
            special_prices = request.form.getlist('variant_special_price[]')
            sync_flags = request.form.getlist('variant_sync_special_price_to_magento[]')
            desired_stocks = request.form.getlist('variant_desired_stock[]')
            actual_stocks = request.form.getlist('variant_stock[]')
            skus = request.form.getlist('variant_magento_sku[]')

            # remove pasted whitespaces
            skus = [sku.strip() for sku in skus]
            variant_manufacturer_ids = [id.strip() for id in variant_manufacturer_ids]
            special_prices = [sp.strip() if sp.strip() else None for sp in special_prices]
            sync_flags = [int(flag) if flag else 1 for flag in sync_flags]

            logging.info(f"variants: {variants}")
            logging.info(f"variant_manufacturer_ids: {variant_manufacturer_ids}")
            logging.info(f"variant_wholesale_prices: {variant_wholesale_prices}")
            logging.info(f"prices: {prices}")
            logging.info(f"special_prices: {special_prices}")
            logging.info(f"sync_flags: {sync_flags}")
            logging.info(f"desired stocks: {desired_stocks}")
            logging.info(f"stocks: {actual_stocks}")
            logging.info(f"skus: {skus}")

            # Check lengths match
            if not (
                len(variants) == len(variant_manufacturer_ids) == len(variant_wholesale_prices) ==
                len(prices) == len(special_prices) == len(sync_flags) == len(desired_stocks) == len(actual_stocks) == len(skus)
            ):
                logging.info("Variant data length mismatch -> returning 400")
                return "Inconsistent variation data submitted.", 400

            # Validate numeric fields
            try:
                for w in variant_wholesale_prices:
                    float(w)
                for p in prices:
                    float(p)
                for sp in special_prices:
                    if sp is not None:
                        float(sp)
                for s in desired_stocks:
                    int(s)
                for st in actual_stocks:
                    int(st)
                # --- Additional validation for growkits: size must be int ---
                if table == "growkits":
                    for v in variants:
                        int(v)
            except ValueError:
                logging.info("Numeric validation failed -> returning 400")
                return "Price, wholesale_price, stock, desired_stock, and (for growkits) size must be numeric/integer.", 400
            
            # 2) Insert each variant
            for i in range(len(prices)):
                product_data = dict(base_data)

                # If we have a distinct variant_attr, set it
                if variant_attr:
                    product_data[variant_attr] = variants[i]

                # Also set manufacturer_id, wholesale_price, etc.
                product_data['manufacturer_id'] = variant_manufacturer_ids[i]
                product_data['wholesale_price'] = variant_wholesale_prices[i]
                product_data['retail_price'] = prices[i]
                product_data['special_price'] = special_prices[i]
                product_data['sync_special_price_to_magento'] = sync_flags[i]
                product_data['desired_stock'] = desired_stocks[i]
                product_data['stock'] = actual_stocks[i]
                product_data['magento_sku'] = skus[i]

                # For debugging, log final product_data
                logging.info(f"Inserting variant {i} with product_data: {product_data}")

                columns = ', '.join(product_data.keys())
                placeholders = ', '.join(['?'] * len(product_data))
                query = f'INSERT INTO {table} ({columns}) VALUES ({placeholders})'
                conn.execute(query, list(product_data.values()))

            conn.commit()
            logging.info("Commit successful for inserted variants.")

            # 3) Redirect after successful insert
            #    (No further reorder—you're done if you want the exact location.)
            manufacturer = base_data.get('manufacturer')
            logging.info(f"Redirecting to manufacturer route: {manufacturer_routes.get(manufacturer, '')}")
            return redirect(f'/{manufacturer_routes.get(manufacturer, "")}')

        # If GET request, render the form
        return render_template(
            'add_product.html',
            table=table,
            fields=base_fields,
            variant_attr=variant_attr,
            unique_values=unique_values
        )

@app.route('/edit_product/<table>/<int:id>', methods=["GET"])
def edit_product(table, id):
    with get_db_connection() as conn:
        allowed_fields = get_allowed_fields(conn, table)
        unique_values = get_unique_values(table)
        cursor = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (id,))
        product = cursor.fetchone()
    if not product:
        return "Product not found", 404
    product_data = dict(product)
    return render_template('edit_product.html', product=product_data, fields=allowed_fields, unique_values=unique_values, table=table)

@app.route('/update_product/<table>/<int:id>', methods=["POST"])
def update_product(table, id):
    with get_db_connection() as conn:
        allowed_fields = get_allowed_fields(conn, table)
        update_data = {}

        # Fetch old product data
        old_product = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (id,)).fetchone()
        if not old_product:
            return "Product not found", 404

        # Gather updated fields from the form
        for field in allowed_fields:
            if field in request.form:
                # Handle checkbox properly (hidden 0 + checkbox 1) by reading all values
                if field == "sync_special_price_to_magento":
                    vals = request.form.getlist(field)
                    value = '1' if '1' in vals else '0'
                else:
                    value = request.form[field].strip()
                # If parent_sku or special_price is blank, store as None (NULL in SQLite)
                if field in ["parent_sku", "special_price"] and value == "":
                    update_data[field] = None
                else:
                    # Only require non-empty value for fields other than parent_sku and special_price
                    if not value and field not in ["parent_sku", "special_price"]:
                        return "All fields must be provided.", 400

                    # Validate numeric fields if needed
                    if field in ["retail_price", "storage_location_number", "wholesale_price", "special_price"]:
                        try:
                            float(value)
                        except ValueError:
                            return f"{field} must be numeric.", 400
                    if field in ["stock", "desired_stock"]:
                        try:
                            int(value)
                        except ValueError:
                            return f"{field} must be an integer.", 400

                    update_data[field] = value

        if not update_data:
            return "No valid fields provided.", 400

        def values_differ(field, new_val, old_val):
            if field in ["retail_price", "storage_location_number", "wholesale_price", "special_price"]:
                try:
                    return float(new_val) != float(old_val)
                except Exception:
                    return new_val != old_val
            elif field in ["stock", "desired_stock", "size", "pack_size", "magento_stock_updates", "available_for_restock", "sync_special_price_to_magento"]:
                try:
                    return int(new_val) != int(old_val)
                except Exception:
                    return new_val != old_val
            else:
                return new_val != old_val

        # Build a dictionary of changes only (fields that differ)
        changes = {field: new_value for field, new_value in update_data.items() 
                   if values_differ(field, new_value, old_product[field])}
        # Now we actually perform the UPDATE on this row
        if changes:
            set_clause = ', '.join([f"{field} = ?" for field in changes.keys()])
            values = [new_val for new_val in changes.values()] + [id]
            query = f'UPDATE {table} SET {set_clause} WHERE id = ?'
            conn.execute(query, values)
            conn.commit()
            change_log = ", ".join([f"{field}: {old_product[field]} -> {new_value}" for field, new_value in changes.items()])
            logging.info(f"Updating product {old_product['name']}, id: {id} in table {table}. Changes: {change_log}")
        else:
            logging.info(f"No changes detected for {old_product['name']}, product id: {id} in table {table}. Skipping update.")
            return redirect(f'/{manufacturer_routes.get(old_product["manufacturer"], "")}')

        #handle magento stock update if needed
        last_refresh_stock, submitted_stock = int(old_product["stock"]), int(update_data["stock"])
        if (last_refresh_stock <= 0 and submitted_stock > 0) or (last_refresh_stock > 0 and submitted_stock == 0):
            async_sync_stock_with_magento(table, id, submitted_stock)

        # Handle magento special price sync if special_price changed and sync_special_price_to_magento is enabled
        if 'special_price' in changes or 'sync_special_price_to_magento' in changes:
            # sqlite3.Row doesn't implement .get(), so access safely via keys()
            sync_flag = int(update_data.get(
                'sync_special_price_to_magento',
                (old_product['sync_special_price_to_magento'] if 'sync_special_price_to_magento' in old_product.keys() else 0)
            ))
            if sync_flag:
                special_price = update_data.get(
                    'special_price',
                    (old_product['special_price'] if 'special_price' in old_product.keys() else None)
                )
                magento_sku = (old_product['magento_sku'] if 'magento_sku' in old_product.keys() else None)
                if magento_sku:
                    # Async sync the special price to magento
                    async_sync_special_price_to_magento(table, id, magento_sku, special_price)

        # Redirect to the correct manufacturer route if known
        manufacturer = update_data.get("manufacturer", old_product["manufacturer"])
        return redirect(f'/{manufacturer_routes.get(manufacturer, "")}')

@app.route('/delete_product/<table>/<int:id>', methods=["POST"])
def delete_product(table, id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT name, manufacturer FROM {table} WHERE id = ?", (id,))
        product = cursor.fetchone()
        if not product:
            return "Product not found", 404
        manufacturer = product['manufacturer']
        cursor.execute(f"DELETE FROM {table} WHERE id = ?", (id,))
        conn.commit()
    logging.info(f"Product {product['name']} {id = } deleted successfully from table {table}.")
    return redirect(f'/{manufacturer_routes.get(manufacturer, "")}')

def ensure_log_file(log_path):
    if not os.path.exists(log_path):
        try:
            # Create the directory if it doesn't exist
            os.makedirs(os.path.dirname(log_path) or '.', exist_ok=True)
            # Create the file if it doesn't exist
            with open(log_path, 'w') as f:
                f.write("Log file created.\n") # Optional: write an initial line
            print(f"Log file created at: {log_path}")
        except OSError as e:
            print(f"Error creating log file {log_path}: {e}")
            return False
    return True

@app.route('/log')
def show_log():
    LINES_PER_PAGE = 100
    log_content = ""
    all_lines = []
    filtered_lines = []
    error_message = None

    # Get parameters from URL (query string)
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1  # Default to page 1 if invalid value
    if page < 1:
        page = 1  # Ensure page is not less than 1

    search_date = request.args.get('date', '')  # Get date string, default to empty
    q = (request.args.get('q', '') or '').strip()
    try:
        days = int(request.args.get('days', '7') or '7')
        if days < 1:
            days = 7
    except ValueError:
        days = 7

    # Ensure the log file exists before trying to read
    if not ensure_log_file(log):
        error_message = f"Error accessing or creating log file at {log}."
        log_content = error_message
        total_pages = 1
        current_page = 1
    else:
        try:
            with open(log, 'r') as log_file:
                all_lines = log_file.readlines()

            # Group lines by log entry (starting at timestamp line)
            timestamp_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2})')
            groups = []  # list[list[str]]
            buffer = []
            for line in all_lines:
                if timestamp_pattern.match(line):
                    if buffer:
                        groups.append(buffer)
                    buffer = [line]
                else:
                    if buffer:
                        buffer.append(line)
                    else:
                        # If no buffer started yet (file may start with non-timestamp), start one
                        buffer = [line]
            if buffer:
                groups.append(buffer)

            # Apply filters
            if search_date:
                # Keep groups whose first line begins with the chosen date
                sel_groups = [g for g in groups if g and g[0].startswith(search_date)]
            elif q:
                # Keep groups within the last N days whose content contains q (case-insensitive)
                from datetime import datetime, timedelta
                now = datetime.now()
                cutoff = now - timedelta(days=days)
                q_lower = q.lower()
                sel_groups = []
                for g in groups:
                    if not g:
                        continue
                    m = timestamp_pattern.match(g[0])
                    if not m:
                        continue
                    try:
                        entry_date = datetime.strptime(m.group(1), '%Y-%m-%d')
                    except Exception:
                        continue
                    if entry_date < cutoff:
                        continue
                    # Check if any line in the group contains the query
                    text = ''.join(g).lower()
                    if q_lower in text:
                        sel_groups.append(g)
            else:
                # No filters: select all groups
                sel_groups = groups

            # Flatten selected groups back into lines
            filtered_lines = []
            for g in sel_groups:
                filtered_lines.extend(g)

            # Reverse the lines to show newest first (applied *after* filtering)
            filtered_lines.reverse()

            # --- Pagination Calculation ---
            total_lines = len(filtered_lines)
            total_pages = ceil(total_lines / LINES_PER_PAGE)
            if total_pages == 0:
                total_pages = 1  # Ensure at least one page even if empty

            # Adjust page number if it's out of bounds after filtering
            if page > total_pages:
                page = total_pages

            # Calculate slice indices
            start_index = (page - 1) * LINES_PER_PAGE
            end_index = start_index + LINES_PER_PAGE

            # Get the lines for the current page
            lines_for_page = filtered_lines[start_index:end_index]

            log_content = '\n'.join(lines_for_page)

            if not log_content and total_lines == 0:
                if search_date:
                    log_content = f"No log entries found for date: {search_date}."
                elif q:
                    log_content = f"No log entries found for query: {q}."
                else:
                    log_content = "Log file is empty or contains no matching entries."
            elif not log_content and total_lines > 0:
                log_content = "No more log entries found for this page/filter."

        except FileNotFoundError:
            error_message = f"Log file not found at {log}."
            log_content = error_message
            total_pages = 1
            page = 1
        except Exception as e:
            error_message = f"An error occurred: {e}"
            log_content = error_message
            total_pages = 1
            page = 1

    # Pass necessary variables to the template
    return render_template(
        'log.html',
        log_content=log_content,
        current_page=page,
        total_pages=total_pages,
        search_date=search_date,  # Pass search date back to pre-fill form
        error_message=error_message,
        q=q,
        days=days
    )

@app.route('/bulk_edit/<table>/<field>', methods=["GET", "POST"])
def bulk_edit(table, field):
    if table not in ALLOWED_TABLES:
        return "Invalid table specified.", 400
    with get_db_connection() as conn:
        allowed_fields = get_allowed_fields(conn, table)
        # Allow special field option for editing both special_price and sync together
        if field != "special_price_and_sync" and field not in allowed_fields:
            return "Invalid field specified.", 400

        # POST: Process bulk updates.
        if request.method == "POST":
            # Check if this is a JSON request (new batched format) or form data (old format)
            is_json = request.is_json
            
            if is_json:
                # New JSON-based batched format
                try:
                    data = request.get_json()
                    updates = data.get('updates', [])
                    batch_num = data.get('batch', 0)
                    total_batches = data.get('total_batches', 1)
                    
                    logging.info(f"Bulk edit batch received: batch {batch_num + 1}/{total_batches}, {len(updates)} updates")
                    
                    # Group updates by product_id to handle special_price_and_sync case
                    updates_by_product = {}
                    for update in updates:
                        product_id = str(update['id'])
                        upd_field = update['field']
                        upd_value = update['value']
                        
                        if product_id not in updates_by_product:
                            updates_by_product[product_id] = {}
                        
                        # Handle field name mapping for sync flag
                        if upd_field == 'sync_special_price_to_magento':
                            updates_by_product[product_id]['sync_special_price_to_magento'] = upd_value
                        else:
                            updates_by_product[product_id][upd_field] = upd_value
                    
                    # Process each product's updates
                    for product_id, field_updates in updates_by_product.items():
                        try:
                            product_id_int = int(product_id)
                        except (ValueError, TypeError):
                            logging.error(f"Invalid product_id: {product_id}")
                            continue
                        
                        # Special handling for special_price_and_sync mode
                        if field == "special_price_and_sync":
                            cur = conn.execute(f"SELECT name, special_price, sync_special_price_to_magento, magento_sku FROM {table} WHERE id = ?", (product_id_int,))
                            row = cur.fetchone()
                            if not row:
                                continue
                            
                            old_special_price = row['special_price']
                            old_sync_flag = row['sync_special_price_to_magento']
                            magento_sku = row['magento_sku']
                            new_special_price = field_updates.get('special_price', old_special_price)
                            new_sync_flag = field_updates.get('sync_special_price_to_magento', old_sync_flag)
                            
                            # Update special_price if it changed
                            if new_special_price != old_special_price:
                                conn.execute(f"UPDATE {table} SET special_price = ? WHERE id = ?", (new_special_price, product_id_int))
                                logging.info(f"Updated product {row['name']}: special_price changed from {old_special_price} to {new_special_price}")
                            
                            # Update sync flag if it changed
                            if new_sync_flag != old_sync_flag:
                                conn.execute(f"UPDATE {table} SET sync_special_price_to_magento = ? WHERE id = ?", (new_sync_flag, product_id_int))
                                logging.info(f"Updated product {row['name']}: sync_special_price_to_magento changed from {old_sync_flag} to {new_sync_flag}")
                            
                            # Trigger Magento sync if enabled and something changed
                            final_sync_enabled = int(new_sync_flag) == 1
                            should_sync = final_sync_enabled and (new_special_price != old_special_price or new_sync_flag != old_sync_flag)
                            if magento_sku and should_sync:
                                price_to_send = new_special_price if new_special_price != old_special_price else old_special_price
                                async_sync_special_price_to_magento(table, product_id_int, magento_sku, price_to_send)
                        else:
                            # Regular field update
                            for upd_field, upd_value in field_updates.items():
                                cur = conn.execute(f"SELECT name, {upd_field} FROM {table} WHERE id = ?", (product_id_int,))
                                row = cur.fetchone()
                                if not row:
                                    continue
                                
                                old_value = row[upd_field]
                                if old_value != upd_value:
                                    conn.execute(f"UPDATE {table} SET {upd_field} = ? WHERE id = ?", (upd_value, product_id_int))
                                    logging.info(f"Updated product {row['name']}: {upd_field} changed from {old_value} to {upd_value}")
                                    
                                    # Handle stock-to-Magento sync
                                    if upd_field == "stock":
                                        if (old_value <= 0 and upd_value > 0) or (old_value > 0 and upd_value == 0):
                                            async_sync_stock_with_magento(table, product_id_int, upd_value)
                    
                    conn.commit()
                    return jsonify({"status": "success", "batch": batch_num, "total_batches": total_batches, "updates_processed": len(updates)})
                
                except Exception as e:
                    logging.error(f"Error processing JSON bulk edit: {str(e)}")
                    conn.rollback()
                    return jsonify({"status": "error", "message": str(e)}), 400
            
            else:
                # Old form-data format (backward compatibility)
                updates = {}
                sync_updates = {}
                
                for key, _ in request.form.items():
                    if key in ["tableSelect", "attrSelect"]:
                        continue
                    
                    # Handle special_price updates
                    if key.startswith('special_price_'):
                        product_id = key.replace('special_price_', '')
                        try:
                            val = request.form.get(key, '').strip()
                            new_value = float(val) if val else None
                        except ValueError:
                            return "special_price must be numeric or blank.", 400
                        updates[product_id] = ('special_price', new_value)
                    # Handle sync flag updates
                    elif key.startswith('sync_flag_'):
                        product_id = key.replace('sync_flag_', '')
                        values = request.form.getlist(key)
                        posted_sync = 1 if '1' in values else 0
                        if product_id not in sync_updates:
                            sync_updates[product_id] = []
                        sync_updates[product_id].append(('sync_special_price_to_magento', posted_sync))
                    # Handle regular field updates
                    else:
                        if field == 'special_price':
                            val = request.form.get(key, '').strip()
                            try:
                                new_value = float(val) if val else None
                            except ValueError:
                                return "special_price must be numeric or blank.", 400
                            updates[key] = new_value
                        else:
                            try:
                                if field in ["retail_price", "wholesale_price", "storage_location_number"]:
                                    new_value = float(request.form.get(key, ''))
                                elif field in ["stock", "desired_stock", "magento_stock_updates", "available_for_restock"]:
                                    new_value = int(request.form.get(key, ''))
                                elif field in ('manufacturer_id', 'magento_sku', 'parent_sku'):
                                    new_value = request.form.get(key, '').strip()
                                else:
                                    # Fallback: treat as raw string (trimmed)
                                    new_value = request.form.get(key, '').strip()
                            except ValueError:
                                return f"Invalid value for {field}.", 400
                            updates[key] = new_value

                # Process updates (form data)
                for product_id, val in list(updates.items()):
                    if isinstance(val, tuple):
                        field_name, new_value = val
                    else:
                        field_name = field
                        new_value = val
                    
                    if field == "special_price_and_sync":
                        cur = conn.execute(f"SELECT name, special_price, sync_special_price_to_magento, magento_sku FROM {table} WHERE id = ?", (product_id,))
                        row = cur.fetchone()
                        if not row:
                            continue
                        
                        old_special_price = row['special_price']
                        old_sync_flag = row['sync_special_price_to_magento']
                        magento_sku = row['magento_sku']
                        
                        if new_value != old_special_price:
                            conn.execute(f"UPDATE {table} SET special_price = ? WHERE id = ?", (new_value, product_id))
                            logging.info(f"Updated product {row['name']}: special_price changed from {old_special_price} to {new_value}")
                        
                        if product_id in sync_updates and sync_updates[product_id]:
                            posted_sync_value = sync_updates[product_id][-1][1]
                        else:
                            posted_sync_value = old_sync_flag

                        if posted_sync_value != old_sync_flag:
                            conn.execute(f"UPDATE {table} SET sync_special_price_to_magento = ? WHERE id = ?", (posted_sync_value, product_id))
                            logging.info(f"Updated product {row['name']}: sync_special_price_to_magento changed from {old_sync_flag} to {posted_sync_value}")

                        final_sync_enabled = int(posted_sync_value) == 1
                        should_sync = final_sync_enabled and (new_value != old_special_price or posted_sync_value != old_sync_flag)
                        if magento_sku and should_sync:
                            price_to_send = new_value if new_value != old_special_price else old_special_price
                            async_sync_special_price_to_magento(table, product_id, magento_sku, price_to_send)
                    else:
                        cur = conn.execute(f"SELECT name, {field} FROM {table} WHERE id = ?", (product_id,))
                        row = cur.fetchone()
                        old_value = row[field] if row else new_value
                        if old_value != new_value:
                            query = f"UPDATE {table} SET {field} = ? WHERE id = ?"
                            conn.execute(query, (new_value, product_id))
                            logging.info(f"Updated product {row['name']}: {field} changed from {old_value} to {new_value}")

                            if field == "stock":
                                last_refresh_str = request.form.get(f"last_refresh_{product_id}")
                                if last_refresh_str is not None:
                                    try:
                                        last_refresh_stock = int(last_refresh_str)
                                    except ValueError:
                                        last_refresh_stock = int(old_value)
                                else:
                                    last_refresh_stock = int(old_value)
                                submitted_stock = int(new_value)
                                if (last_refresh_stock <= 0 and submitted_stock > 0) or (last_refresh_stock > 0 and submitted_stock == 0):
                                    async_sync_stock_with_magento(table, product_id, submitted_stock)
                
                conn.commit()
                return redirect(request.headers.get('Referer', '/'))

        # GET: Query and group data based on the table.
        all_manufacturers = set()
        
        # (No special-casing here; let the table-specific grouping below run)
        
        if table == 'cannabis_seeds':
            cursor = conn.execute("SELECT * FROM cannabis_seeds ORDER BY manufacturer, storage_location_number;")
            rows = cursor.fetchall()
            groups = defaultdict(lambda: defaultdict(list))
            pack_sizes = defaultdict(set)
            for row in rows:
                st = row['seed_type']
                key = (row['name'], row['manufacturer'])
                groups[st][key].append(row)
                pack_sizes[st].add(row['pack_size'])
                all_manufacturers.add(row['manufacturer'])
            for st in pack_sizes:
                pack_sizes[st] = sorted(pack_sizes[st])
            context = {
                "grouping": "cannabis_seeds",
                "groups": groups,
                "variant_headers": pack_sizes,
                "table": table,
                "field": field,
                "all_manufacturers": sorted(all_manufacturers)
            }
        elif table == 'spores' or table == 'cultures':
            cursor = conn.execute(f"SELECT * FROM {table} ORDER BY manufacturer, name, form;")
            rows = cursor.fetchall()
            groups = {}           # group by product name
            variant_headers = {}  # variant values per product (forms)
            all_forms = set()     # union of all forms
            for row in rows:
                name = row['name']
                groups.setdefault(name, []).append(row)
                form = row['form']
                all_forms.add(form)
                variant_headers.setdefault(name, set()).add(form)
                all_manufacturers.add(row['manufacturer'])
            for name in variant_headers:
                variant_headers[name] = sorted(variant_headers[name])
            all_forms = sorted(all_forms)
            context = {
                "grouping": table,
                "groups": groups,
                "variant_headers": variant_headers,
                "all_variants": all_forms,
                "table": table,
                "field": field,
                "all_manufacturers": sorted(all_manufacturers)
            }
        elif table == 'growkits':
            cursor = conn.execute("SELECT * FROM growkits ORDER BY manufacturer, name, size;")
            rows = cursor.fetchall()
            groups = {}           # group by (name, manufacturer)
            variant_headers = {}  # variant values per product (sizes)
            all_sizes = set()     # union of all sizes
            for row in rows:
                key = (row['name'], row['manufacturer'])
                groups.setdefault(key, []).append(row)
                size = row['size']
                all_sizes.add(size)
                variant_headers.setdefault(key, set()).add(size)
                all_manufacturers.add(row['manufacturer'])
            for key in variant_headers:
                variant_headers[key] = sorted(variant_headers[key])
            all_sizes = sorted(all_sizes)
            context = {
                "grouping": "growkits",
                "groups": groups,
                "variant_headers": variant_headers,
                "all_variants": all_sizes,
                "table": table,
                "field": field,
                "all_manufacturers": sorted(all_manufacturers)
            }
        elif table == 'misc':
            cursor = conn.execute("SELECT * FROM misc ORDER BY manufacturer, name;")
            rows = cursor.fetchall()
            # For misc, assume one row per product.
            groups = {row['name']: row for row in rows}
            manufacturers = sorted({row['manufacturer'] for row in rows})
            all_manufacturers = manufacturers
            context = {
                "grouping": "misc",
                "groups": groups,
                "table": table,
                "field": field,
                "manufacturers": manufacturers,
                "all_manufacturers": all_manufacturers
            }
        # SSR initial state for bulk edit filters
        context.update({
            'active_tab': request.args.get('tab', 'all'),
            'initial_manufacturer': request.args.get('manufacturer') or ''
        })
        return render_template('bulk_edit.html', **context)

@app.route('/order/<manufacturer>')
def order_by_manufacturer(manufacturer):
    all_manufacturers = get_distinct_manufacturers()
    with get_db_connection() as conn:
        products = []
        sku_to_product = {}
        # Cannabis seeds
        seeds = conn.execute("SELECT name, stock, desired_stock, pack_size, available_for_restock, magento_sku FROM cannabis_seeds WHERE manufacturer=? ORDER BY name, pack_size", (manufacturer,)).fetchall()
        for s in seeds:
            if ('available_for_restock' in s.keys() and not s['available_for_restock']):
                continue
            sku = s['magento_sku'] if 'magento_sku' in s.keys() else None
            label = f"{s['name']} (Seeds, {s['pack_size']})"
            products.append({
                'product': label,
                'current_stock': s['stock'],
                'desired_stock': s['desired_stock'],
                'available_for_restock': s['available_for_restock'] if 'available_for_restock' in s.keys() else 1,
                'sku': sku
            })
            if sku:
                sku_to_product[sku] = label
        # Growkits
        growkits = conn.execute("SELECT name, stock, desired_stock, size, available_for_restock, magento_sku FROM growkits WHERE manufacturer=? ORDER BY name, size", (manufacturer,)).fetchall()
        for g in growkits:
            if ('available_for_restock' in g.keys() and not g['available_for_restock']):
                continue
            sku = g['magento_sku'] if 'magento_sku' in g.keys() else None
            label = f"{g['name']} (Growkit, {g['size']})"
            products.append({
                'product': label,
                'current_stock': g['stock'],
                'desired_stock': g['desired_stock'],
                'available_for_restock': g['available_for_restock'] if 'available_for_restock' in g.keys() else 1,
                'sku': sku
            })
            if sku:
                sku_to_product[sku] = label
        # Spores
        spores = conn.execute("SELECT name, stock, desired_stock, form, available_for_restock, magento_sku FROM spores WHERE manufacturer=? ORDER BY name, form", (manufacturer,)).fetchall()
        for sp in spores:
            if ('available_for_restock' in sp.keys() and not sp['available_for_restock']):
                continue
            sku = sp['magento_sku'] if 'magento_sku' in sp.keys() else None
            label = f"{sp['name']} (Spore, {sp['form']})"
            products.append({
                'product': label,
                'current_stock': sp['stock'],
                'desired_stock': sp['desired_stock'] if 'desired_stock' in sp.keys() else 0,
                'available_for_restock': sp['available_for_restock'] if 'available_for_restock' in sp.keys() else 1,
                'sku': sku
            })
            if sku:
                sku_to_product[sku] = label
        # Cultures
        cultures = conn.execute("SELECT name, stock, desired_stock, form, available_for_restock, magento_sku FROM cultures WHERE manufacturer=? ORDER BY name, form", (manufacturer,)).fetchall()
        for cu in cultures:
            if ('available_for_restock' in cu.keys() and not cu['available_for_restock']):
                continue
            sku = cu['magento_sku'] if 'magento_sku' in cu.keys() else None
            label = f"{cu['name']} (Culture, {cu['form']})"
            products.append({
                'product': label,
                'current_stock': cu['stock'],
                'desired_stock': cu['desired_stock'] if 'desired_stock' in cu.keys() else 0,
                'available_for_restock': cu['available_for_restock'] if 'available_for_restock' in cu.keys() else 1,
                'sku': sku
            })
            if sku:
                sku_to_product[sku] = label
        # Misc
        misc = conn.execute("SELECT name, stock, desired_stock, available_for_restock, magento_sku FROM misc WHERE manufacturer=? ORDER BY name", (manufacturer,)).fetchall()
        for m in misc:
            if ('available_for_restock' in m.keys() and not m['available_for_restock']):
                continue
            sku = m['magento_sku'] if 'magento_sku' in m.keys() else None
            label = f"{m['name']} (Misc)"
            products.append({
                'product': label,
                'current_stock': m['stock'],
                'desired_stock': m['desired_stock'] if 'desired_stock' in m.keys() else 0,
                'available_for_restock': m['available_for_restock'] if 'available_for_restock' in m.keys() else 1,
                'sku': sku
            })
            if sku:
                sku_to_product[sku] = label

    # Get processing quantities for all SKUs
    all_skus = set(p['sku'] for p in products if p.get('sku'))
    sku_processing_counter = stock_app_proposed_order_data_fetcher.fetch_processing_sku_counter(all_skus)
    # Map processing quantities to product labels
    product_processing = {sku_to_product[sku]: qty for sku, qty in sku_processing_counter.items() if sku in sku_to_product}

    # Calculate order summary: difference between desired_stock and stock
    product_data = {}
    totals = {'current_stock': 0, 'desired_stock': 0, 'order_qty': 0, 'processing_quantity': 0}
    for p in products:
        current = p['current_stock'] or 0
        desired = p['desired_stock'] or 0
        processing = product_processing.get(p['product'], 0)
        available_for_restock = p.get('available_for_restock', 1)
        order_qty = max(desired - (current - processing), 0)
        if not available_for_restock:
            order_qty = 0
        product_data[p['product']] = {
            'current_stock': current,
            'desired_stock': desired,
            'processing_quantity': processing,
            'order_qty': order_qty
        }
        totals['current_stock'] += current
        totals['desired_stock'] += desired
        totals['order_qty'] += order_qty
        totals['processing_quantity'] += processing

    # Create a simple order summary string
    order_summary = f"Order for {manufacturer}:\n\n"
    max_qty_width = 5
    for name, data in product_data.items():
        if data['order_qty'] > 0:
            qty = min(data['order_qty'], 1000)
            order_summary += f"{str(qty).rjust(max_qty_width)}  {name}\n"
    if totals['order_qty'] == 0:
        order_summary += "No products need ordering.\n"

    # Render a page similar to proposed_order.html (reuse the template)
    # We'll map the fields to match the template's expectations
    table_data = {}
    for name, data in product_data.items():
        table_data[name] = {
            'current_stock': data['current_stock'],
            'processing_quantity': data['processing_quantity'],
            'adjusted_stock': data['current_stock'] - data['processing_quantity'],
            'desired_quantity': data['desired_stock'],
            'desired_order': data['order_qty'],
            'proposed_quantity': data['order_qty'],
            'remaining_quantity': 0,
        }
    totals_row = {
        'current_stock': totals['current_stock'],
        'processing_quantity': totals['processing_quantity'],
        'adjusted_stock': totals['current_stock'] - totals['processing_quantity'],
        'desired_quantity': totals['desired_stock'],
        'desired_order': totals['order_qty'],
        'proposed_quantity': totals['order_qty'],
        'remaining_quantity': 0,
    }
    return render_template(
        'proposed_order.html',
        route=f'order/{manufacturer}',
        order_summary=order_summary,
        product_data=table_data,
        totals=totals_row,
        all_manufacturers=sorted(all_manufacturers),
        current_manufacturer=manufacturer
    )

@app.route('/api/order/<manufacturer>')
def api_order_by_manufacturer(manufacturer):
    all_manufacturers = get_distinct_manufacturers()
    with get_db_connection() as conn:
        products = []
        sku_to_product = {}
        # Cannabis seeds
        seeds = conn.execute("SELECT name, stock, desired_stock, pack_size, available_for_restock, magento_sku FROM cannabis_seeds WHERE manufacturer=? ORDER BY name, pack_size", (manufacturer,)).fetchall()
        for s in seeds:
            if ('available_for_restock' in s.keys() and not s['available_for_restock']):
                continue
            sku = s['magento_sku'] if 'magento_sku' in s.keys() else None
            label = f"{s['name']} (Seeds, {s['pack_size']})"
            products.append({
                'product': label,
                'current_stock': s['stock'],
                'desired_stock': s['desired_stock'],
                'available_for_restock': s['available_for_restock'] if 'available_for_restock' in s.keys() else 1,
                'sku': sku
            })
            if sku:
                sku_to_product[sku] = label
        # Growkits
        growkits = conn.execute("SELECT name, stock, desired_stock, size, available_for_restock, magento_sku FROM growkits WHERE manufacturer=? ORDER BY name, size", (manufacturer,)).fetchall()
        for g in growkits:
            if ('available_for_restock' in g.keys() and not g['available_for_restock']):
                continue
            sku = g['magento_sku'] if 'magento_sku' in g.keys() else None
            label = f"{g['name']} (Growkit, {g['size']})"
            products.append({
                'product': label,
                'current_stock': g['stock'],
                'desired_stock': g['desired_stock'],
                'available_for_restock': g['available_for_restock'] if 'available_for_restock' in g.keys() else 1,
                'sku': sku
            })
            if sku:
                sku_to_product[sku] = label
        # Spores
        spores = conn.execute("SELECT name, stock, desired_stock, form, available_for_restock, magento_sku FROM spores WHERE manufacturer=? ORDER BY name, form", (manufacturer,)).fetchall()
        for sp in spores:
            if ('available_for_restock' in sp.keys() and not sp['available_for_restock']):
                continue
            sku = sp['magento_sku'] if 'magento_sku' in sp.keys() else None
            label = f"{sp['name']} (Spore, {sp['form']})"
            products.append({
                'product': label,
                'current_stock': sp['stock'],
                'desired_stock': sp['desired_stock'] if 'desired_stock' in sp.keys() else 0,
                'available_for_restock': sp['available_for_restock'] if 'available_for_restock' in sp.keys() else 1,
                'sku': sku
            })
            if sku:
                sku_to_product[sku] = label
        # Cultures
        cultures = conn.execute("SELECT name, stock, desired_stock, form, available_for_restock, magento_sku FROM cultures WHERE manufacturer=? ORDER BY name, form", (manufacturer,)).fetchall()
        for cu in cultures:
            if ('available_for_restock' in cu.keys() and not cu['available_for_restock']):
                continue
            sku = cu['magento_sku'] if 'magento_sku' in cu.keys() else None
            label = f"{cu['name']} (Culture, {cu['form']})"
            products.append({
                'product': label,
                'current_stock': cu['stock'],
                'desired_stock': cu['desired_stock'] if 'desired_stock' in cu.keys() else 0,
                'available_for_restock': cu['available_for_restock'] if 'available_for_restock' in cu.keys() else 1,
                'sku': sku
            })
            if sku:
                sku_to_product[sku] = label
        # Misc
        misc = conn.execute("SELECT name, stock, desired_stock, available_for_restock, magento_sku FROM misc WHERE manufacturer=? ORDER BY name", (manufacturer,)).fetchall()
        for m in misc:
            if ('available_for_restock' in m.keys() and not m['available_for_restock']):
                continue
            sku = m['magento_sku'] if 'magento_sku' in m.keys() else None
            label = f"{m['name']} (Misc)"
            products.append({
                'product': label,
                'current_stock': m['stock'],
                'desired_stock': m['desired_stock'] if 'desired_stock' in m.keys() else 0,
                'available_for_restock': m['available_for_restock'] if 'available_for_restock' in m.keys() else 1,
                'sku': sku
            })
            if sku:
                sku_to_product[sku] = label

    all_skus = set(p['sku'] for p in products if p.get('sku'))
    try:
        sku_processing_counter = stock_app_proposed_order_data_fetcher.fetch_processing_sku_counter(all_skus)
    except Exception as e:
        print("processing fetch failed:", e)
        sku_processing_counter = {}

    product_processing = {sku_to_product[sku]: qty for sku, qty in sku_processing_counter.items() if sku in sku_to_product}

    product_data = {}
    totals = {'current_stock': 0, 'desired_stock': 0, 'order_qty': 0, 'processing_quantity': 0}
    for p in products:
        current = p['current_stock'] or 0
        desired = p['desired_stock'] or 0
        processing = product_processing.get(p['product'], 0)
        available_for_restock = p.get('available_for_restock', 1)
        order_qty = max(desired - (current - processing), 0)
        if not available_for_restock:
            order_qty = 0

        product_data[p['product']] = {
            "current_stock": current,
            "desired_stock": desired,
            "processing_quantity": processing,
            "order_qty": order_qty,
            "sku": p.get("sku"),
        }

        totals['current_stock'] += current
        totals['desired_stock'] += desired
        totals['order_qty'] += order_qty
        totals['processing_quantity'] += processing

    return jsonify({
        "manufacturer": manufacturer,
        "products": product_data,
        "totals": totals,
        "all_manufacturers": sorted(all_manufacturers),
    })

def get_seeds(manufacturer, on_sale=False):
    with get_db_connection() as conn:
        if on_sale:
            cursor = conn.execute("""
                SELECT name, pack_size, stock, retail_price, special_price, sync_special_price_to_magento, id, storage_location_number, seed_type, manufacturer, manufacturers_collection, available_for_restock
                FROM cannabis_seeds 
                WHERE manufacturer=? AND special_price IS NOT NULL
                ORDER BY name, pack_size
            """, (manufacturer,))
        else:
            cursor = conn.execute("""
                SELECT name, pack_size, stock, retail_price, special_price, sync_special_price_to_magento, id, storage_location_number, seed_type, manufacturer, manufacturers_collection, available_for_restock
                FROM cannabis_seeds 
                WHERE manufacturer=?
                ORDER BY name, pack_size
            """, (manufacturer,))
        seeds = cursor.fetchall()
    grouped = defaultdict(lambda: defaultdict(list))
    pack_sizes = set()
    for seed in seeds:
        key = seed['name']
        grouped[key][seed['pack_size']].append(seed)
        pack_sizes.add(seed['pack_size'])
    return grouped, sorted(pack_sizes)

def get_seeds_grouped(manufacturer, on_sale=False):
    with get_db_connection() as conn:
        if on_sale:
            cursor = conn.execute("""
                SELECT name, pack_size, stock, retail_price, special_price, sync_special_price_to_magento, id, storage_location_number, seed_type, manufacturer, manufacturers_collection, available_for_restock
                FROM cannabis_seeds 
                WHERE manufacturer=? AND special_price IS NOT NULL
                ORDER BY seed_type, storage_location_number, name, pack_size
            """, (manufacturer,))
        else:
            cursor = conn.execute("""
                SELECT name, pack_size, stock, retail_price, special_price, sync_special_price_to_magento, id, storage_location_number, seed_type, manufacturer, manufacturers_collection, available_for_restock
                FROM cannabis_seeds 
                WHERE manufacturer=?
                ORDER BY seed_type, storage_location_number, name, pack_size
            """, (manufacturer,))
        seeds = cursor.fetchall()
    grouped = defaultdict(lambda: defaultdict(list))
    pack_sizes = defaultdict(set)
    
    for seed in seeds:
        seed_type = seed['seed_type']
        # Only if the manufacturer is "Fastbuds" and seed_type is "Feminized Autoflower",
        # perform the split. Otherwise, use the original seed_type.
        if manufacturer == "Fastbuds" and seed_type == "Feminized Autoflower":
            collection = seed['manufacturers_collection'].strip()
            if collection == "1st Edition | Premium":
                group_key = "Feminized Autoflower 1st Edition | Premium"
            elif collection == 'Originals':
                group_key = "Feminized Autoflower Originals"
        elif manufacturer == "Fastbuds" and seed_type == "Feminized":
            collection = seed['manufacturers_collection'].strip()
            if collection == "Fast Flowering":
                group_key = "Feminized Fast Flowering"
            else:
                group_key = "Feminized"

        else:
            group_key = seed_type
        
        key = (seed['storage_location_number'], seed['name'])
        grouped[group_key][key].append(seed)
        pack_sizes[group_key].add(seed['pack_size'])
    
    # Convert each pack_sizes set to a sorted list
    for size in pack_sizes:
        pack_sizes[size] = sorted(pack_sizes[size])
    
    return grouped, pack_sizes

def get_mushrooms_grouped():
    with get_db_connection() as conn:
        # Growkits
        products_raw = conn.execute('SELECT * FROM growkits ORDER BY manufacturer, name, size').fetchall()
        growkits_grouped = defaultdict(lambda: defaultdict(list))
        for product in products_raw:
            growkits_grouped[product['manufacturer']][product['name']].append({
                'id': product['id'],
                'stock': product['stock'],
                'retail_price': product['retail_price'],
                'special_price': product['special_price'],
                'size': product['size'],
                'manufacturer': product['manufacturer'],
                'available_for_restock': product['available_for_restock']
            })
        # Spores
        spores_raw = conn.execute('SELECT * FROM spores ORDER BY name, form').fetchall()
        spores_grouped = defaultdict(list)
        for spore in spores_raw:
            spores_grouped[spore['name']].append({
                'id': spore['id'],
                'stock': spore['stock'],
                'retail_price': spore['retail_price'],
                'special_price': spore['special_price'],
                'form': spore['form'],
                'manufacturer': spore['manufacturer'] if 'manufacturer' in spore.keys() else None,
                'available_for_restock': spore['available_for_restock'] if 'available_for_restock' in spore.keys() else 1
            })
        # Cultures
        cultures_raw = conn.execute('SELECT * FROM cultures ORDER BY manufacturer, name').fetchall()
        cultures_grouped = defaultdict(list)
        for culture in cultures_raw:
            cultures_grouped[culture['name']].append({
                'id': culture['id'],
                'stock': culture['stock'],
                'retail_price': culture['retail_price'],
                'special_price': culture['special_price'],
                'form': culture['form'],
                'manufacturer': culture['manufacturer'] if 'manufacturer' in culture.keys() else None,
                'available_for_restock': culture['available_for_restock'] if 'available_for_restock' in culture.keys() else 1
            })
        # Misc
        misc_raw = conn.execute('SELECT * FROM misc ORDER BY manufacturer, name').fetchall()
        misc_grouped = []
        for item in misc_raw:
            misc_grouped.append({
                'id': item['id'],
                'name': item['name'],
                'stock': item['stock'],
                'retail_price': item['retail_price'],
                'special_price': item['special_price'],
                'manufacturer': item['manufacturer'] if 'manufacturer' in item.keys() else None,
                'available_for_restock': item['available_for_restock'] if 'available_for_restock' in item.keys() else 1
            })

    return growkits_grouped, spores_grouped, misc_grouped, cultures_grouped

@app.template_filter('format_number')
def format_number(value):
    try:
        # If the value is effectively an integer, return it as an int.
        if float(value) == int(float(value)):
            return int(float(value))
        else:
            return value
    except (ValueError, TypeError):
        return value

@app.template_filter('format_price_with_special')
def format_price_with_special(retail_price, special_price=None):
    """
    Format price display: if special_price exists, show retail_price struck through 
    followed by the special_price in bold/red.
    """
    # Allow user to hide visual on-sale indication via cookie toggle
    try:
        show_specials = (request.cookies.get('show_special_prices', '1') == '1')
    except Exception:
        show_specials = True

    # When hidden, always render the regular retail price only
    if not show_specials:
        try:
            return f"€{float(retail_price):.2f}"
        except (ValueError, TypeError):
            return str(retail_price)

    if not special_price:
        try:
            return f"€{float(retail_price):.2f}"
        except (ValueError, TypeError):
            return str(retail_price)
    
    try:
        retail = float(retail_price)
        special = float(special_price)
        return f'<s style="color: gray;">€{retail:.2f}</s> <strong style="color: red;">€{special:.2f}</strong>'
    except (ValueError, TypeError):
        return str(retail_price)

@app.template_filter('highlight_log')
def highlight_log(log_text):
    """
    Highlights specific fields in the log text with span tags and CSS classes.
    """
    if not log_text:
        return log_text

    # Helper: match after start of line or comma, allow spaces
    def field_regex(field, value_pattern):
        # Matches: field, optional spaces, colon, optional spaces, value
        return rf'({field}\s*:\s*)({value_pattern})'

    # For numbers (int, float, negative, decimal)
    number_pattern = r'-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?'

    # Highlight retail_price: handle both "num -> num" and with optional percentage
    pct_pattern = rf'(?:\s*\(\s*-?{number_pattern}%\s*\))?'
    arrow_pattern = rf'{number_pattern}\s*->\s*{number_pattern}{pct_pattern}'
    # First, replace the arrow form so it doesn't get split by the single-number rule
    log_text = re.sub(
        field_regex('retail_price', arrow_pattern),
        r'\1<span class="retail-price">\2</span>',
        log_text,
        flags=re.IGNORECASE
    )
    # Then handle the simple single-number retail_price
    log_text = re.sub(
        field_regex('retail_price', number_pattern),
        r'\1<span class="retail-price">\2</span>',
        log_text,
        flags=re.IGNORECASE
    )

    # Highlight storage_location_number: value
    log_text = re.sub(
        field_regex('storage_location_number', number_pattern),
        r'\1<span class="storage-location">\2</span>',
        log_text,
        flags=re.IGNORECASE
    )

    # Highlight seed_type: value
    def seed_type_repl(match):
        prefix = match.group(1)
        value = match.group(2).strip()
        val_lower = value.lower()
        if val_lower == "feminized":
            css = "seed-type-feminized"
        elif val_lower in ("feminized autoflower", "autoflower", "auto"):
            css = "seed-type-feminized-autoflower"
        elif val_lower == "regular":
            css = "seed-type-regular"
        else:
            css = "seed-type-other"
        return f'{prefix}<span class="{css}">{value}</span>'
    log_text = re.sub(
        field_regex('seed_type', r'[^,\n]+'),
        seed_type_repl,
        log_text,
        flags=re.IGNORECASE
    )

    # Highlight name: value
    log_text = re.sub(
        field_regex('name', r'[^,\n]+'),
        r'\1<span class="name">\2</span>',
        log_text,
        flags=re.IGNORECASE
    )

    # Highlight pack_size: value
    log_text = re.sub(
        field_regex('pack_size', number_pattern),
        r'\1<span class="pack-size">\2</span>',
        log_text,
        flags=re.IGNORECASE
    )

    # Highlight manufacturer: value
    log_text = re.sub(
        field_regex('manufacturer', r'[^,\n]+'),
        r'\1<span class="manufacturer">\2</span>',
        log_text,
        flags=re.IGNORECASE
    )

    # Highlight stock: value
    log_text = re.sub(
        field_regex('stock', number_pattern),
        r'\1<span class="stock">\2</span>',
        log_text,
        flags=re.IGNORECASE
    )

    # Highlight form: value
    log_text = re.sub(
        field_regex('form', r'[^,\n]+'),
        r'\1<span class="pack-size">\2</span>',
        log_text,
        flags=re.IGNORECASE
    )

    # Handle dictionary-like structures (e.g., {'field': 'value'})
    dict_field_pattern = r"'([^']+)':\s*'([^']+)'"
    log_text = re.sub(
        dict_field_pattern,
        lambda match: f"'{match.group(1)}': '<span class=\"{match.group(1).replace('_', '-').lower()}\">{match.group(2)}</span>'",
        log_text
    )

    return log_text

def get_grow_kit_order_proposal():

    def calculate_adjusted_stock(current_stock, processing_orders):
        """
        Subtract processing orders from current stock.
        Allow negative values so that if processing orders exceed current stock,
        the deficit is carried forward.
        """
        adjusted = Counter(current_stock)
        adjusted.subtract(processing_orders)
        logging.debug("Adjusted stock: %s", adjusted)
        return adjusted

    def compute_proposed_order(preferred_stock, adjusted_stock):
        """
        Compute the shortage that needs to be ordered.
        """
        proposed = preferred_stock - adjusted_stock
        # Remove negative quantities (set them to 0)
        for product in proposed:
            proposed[product] = max(proposed[product], 0)
        logging.debug("Proposed order after computation: %s", proposed)
        return proposed

    def order_exception_product(product, proposed, proposed_quantities, order_summary, threshold=15):
        """
        For exception products (Golden Teacher, McKennaii), if their shortage is >= threshold,
        order full boxes (20 units per box) until the shortage falls below the threshold.
        These products will not be included in any mixed box.
        """
        logging.debug("Processing exception product: %s, initial proposed: %s", product, proposed[product])
        while proposed[product] >= threshold:
            proposed_quantities[product] += 20
            order_summary.append(f"1 doos 1200cc {product}")
            logging.debug("Ordered 20 of %s. Before subtracting: %s", product, proposed[product])
            proposed[product] -= 20
            logging.debug("After subtracting, proposed[%s]: %s", product, proposed[product])
    
    def fill_one_mixed_box(proposed, proposed_quantities):
        """
        Attempt to fill one mixed box (20 kits) using the available shortage in proposed.
        Recalculate the available non-exception products on each iteration.
        Returns a Counter representing one full box if successful, else None.
        """
        box = Counter()
        total_added = 0

        logging.debug("Starting fill_one_mixed_box, initial proposed: %s", dict(proposed))
        # Continue until we have allocated 20 kits from non-exception products
        while total_added < 20:
            # Recalculate the available non-exception products every iteration
            available = sorted(
                [p for p in proposed if p not in ["Golden Teacher", "McKennaii"] and proposed[p] > 0],
                key=lambda p: proposed[p],
                reverse=True
            )
            available_total = sum(proposed[p] for p in proposed if p not in ["Golden Teacher", "McKennaii"] and proposed[p] > 0)
            logging.debug("Available products for allocation: %s, total available: %s", available, available_total)
            if available_total < (20 - total_added):
                logging.debug("Not enough kits available to complete the box. Total added: %s", total_added)
                break

            for product in available:
                if total_added >= 20:
                    break
                if proposed[product] > 0:
                    logging.debug("Adding 1 unit of %s. Proposed before: %s", product, proposed[product])
                    box[product] += 1
                    proposed[product] -= 1
                    proposed_quantities[product] += 1
                    total_added += 1
                    logging.debug("After adding, proposed[%s]: %s, total_added: %s", product, proposed[product], total_added)

        logging.debug("Finished allocation loop: total_added=%s, box=%s", total_added, dict(box))
        if total_added == 20:
            return box
        else:
            # Roll back the units taken if a full box wasn't filled.
            logging.debug("Incomplete box (total_added=%s). Rolling back changes: box=%s", total_added, dict(box))
            for product, qty in box.items():
                proposed[product] += qty
                proposed_quantities[product] -= qty
            return None

    # Fetch current stock and desired stock from database for 1200cc kits
    with get_db_connection() as conn:
        products = conn.execute(
            'SELECT name, stock, desired_stock FROM growkits WHERE size=1200 AND manufacturer="Fresh Mushrooms" ORDER BY name'
        ).fetchall()
        preferred_stock = Counter({product['name']: product['desired_stock'] for product in products})
        current_stock = Counter({product['name']: product['stock'] for product in products})
    
    logging.debug("Preferred stock: %s", preferred_stock)
    logging.debug("Current stock: %s", current_stock)
    
    # Fetch processing orders
    processing_orders = stock_app_proposed_order_data_fetcher.fetch_processing_grow_kit_Counter()
    logging.debug("Processing orders: %s", processing_orders)
    
    # Calculate adjusted stock and proposed order shortage
    adjusted_stock = calculate_adjusted_stock(current_stock, processing_orders)
    proposed = compute_proposed_order(preferred_stock, adjusted_stock)
    
    proposed_quantities = Counter()  # Track how many units are proposed for ordering
    remaining_quantities = Counter()
    order_summary = []
    
    # Only propose an order if total non-exception shortage is at least one full box (20 kits)
    non_exception_total = sum(proposed[p] for p in proposed if p not in ["Golden Teacher", "McKennaii"])
    logging.debug("Total non-exception proposed quantity: %s", non_exception_total)
    
    if proposed.total() >= 20:
        order_summary.append("freshmushrooms@freshmushrooms.nl\n")
        order_summary.append("Hoi Astrid,\n\nIk zou graag bestellen:\n")
        
        # Process exception products separately
        for exception in ["Golden Teacher", "McKennaii"]:
            order_exception_product(exception, proposed, proposed_quantities, order_summary, threshold=15)
        
        logging.debug("Proposed after exception processing: %s", dict(proposed))
        
        # Process mixed boxes for non-exception products using their total only
        while sum(proposed[p] for p in proposed if p not in ["Golden Teacher", "McKennaii"] and proposed[p] > 0) >= 20:
            box = fill_one_mixed_box(proposed, proposed_quantities)
            logging.debug("Result of fill_one_mixed_box: %s", dict(box) if box else "None")
            if box:
                order_summary.append("1 doos 1200cc met:")
                for product, qty in box.items():
                    order_summary.append(f"  {qty} {product}")
            else:
                break
        
        order_summary.append("\nGroeten,\nFrans\n")
        
        # List any remaining kits (that didn't fill a full box) from non-exception products
        remaining_total = sum(proposed[p] for p in proposed if p not in ["Golden Teacher", "McKennaii"] and proposed[p] > 0)
        if remaining_total > 0:
            order_summary.append(f"\n{remaining_total} remaining kits (no full mix, GT or MCK box of 20):")
            for product in proposed:
                if product not in ["Golden Teacher", "McKennaii"] and proposed[product] > 0:
                    order_summary.append(f"  {proposed[product]} {product}")
                    remaining_quantities[product] += proposed[product]
    else:
        order_summary.append("No grow kit order needed with the current stock.")
    
    # Prepare detailed product data for the template
    all_products = set(preferred_stock.keys()) | set(current_stock.keys()) | set(processing_orders.keys()) | set(proposed_quantities.keys())
    product_data = {}
    desired_order = preferred_stock - adjusted_stock
    for product in all_products:
        product_data[product] = {
            'desired_quantity': preferred_stock.get(product, 0),
            'current_stock': current_stock.get(product, 0),
            'processing_quantity': processing_orders.get(product, 0),
            'adjusted_stock': adjusted_stock.get(product, 0),
            'desired_order': max(desired_order.get(product, 0), 0),
            'proposed_quantity': proposed_quantities.get(product, 0),
            'remaining_quantity': remaining_quantities.get(product, 0),
        }
    
    totals = {
        'current_stock': sum(data['current_stock'] for data in product_data.values()),
        'processing_quantity': sum(data['processing_quantity'] for data in product_data.values()),
        'adjusted_stock': sum(data['adjusted_stock'] for data in product_data.values()),
        'desired_quantity': sum(data['desired_quantity'] for data in product_data.values()),
        'desired_order': sum(data['desired_order'] for data in product_data.values()),
        'proposed_quantity': sum(data['proposed_quantity'] for data in product_data.values()),
        'remaining_quantity': sum(data['remaining_quantity'] for data in product_data.values())
    }
    
    logging.debug("Final order summary:\n%s", "\n".join(order_summary))
    logging.debug("Final product data: %s", product_data)
    logging.debug("Totals: %s", totals)
    
    return {
        'order_summary': "\n".join(order_summary),
        'product_data': product_data,
        'totals': totals
    }

@app.route('/find_product_by_sku/<sku>', methods=['GET'])
def find_product_by_sku(sku):
    """
    Look up a product by magento_sku across all tables.
    Returns: {table, id, stock, ...}
    """
    for table in query_table.keys():
        with get_db_connection() as conn:
            cursor = conn.execute(f"SELECT id, stock FROM {table} WHERE magento_sku = ?", (sku,))
            row = cursor.fetchone()
            if row:
                return jsonify({
                    "table": table,
                    "id": row["id"],
                    "stock": row["stock"]
                })
    return jsonify({"error": "SKU not found"}), 404

@app.route('/get_product_info/<table>/<int:id>', methods=['GET'])
def get_product_info(table, id):
    """
    Return product info for a given table/id.
    """
    if table not in query_table:
        return jsonify({"error": "Invalid table"}), 400
    with get_db_connection() as conn:
        to_select = ', '.join(query_table[table])
        cursor = conn.execute(f"SELECT {to_select} FROM {table} WHERE id = ?", (id,))
        row = cursor.fetchone()
        if row:
            return jsonify({col: row[col] for col in query_table[table]})
        else:
            return jsonify({"error": "Product not found"}), 404

def get_allowed_fields(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    allowed_fields = [col[1] for col in columns if col[5] == 0]  # column name is at index 1, pk flag at index 5
    return allowed_fields

def get_unique_values(table_name):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        exclusions = {'id', 'name', 'retail_price', 'wholesale_price', 'stock', 'storage_location_number', 'parent_sku'}
        allowed_columns = [col[1] for col in columns_info if col[1] not in exclusions and col[5] == 0]
        unique_values = {}
        for column in allowed_columns:
            cursor.execute(f"SELECT DISTINCT {column} FROM {table_name}")
            fetched_values = cursor.fetchall()
            unique_values[column] = [val[0] for val in fetched_values]
    return unique_values

def get_stock_item(sku: str, headers: dict) -> dict:
    """
    Fetches the Magento stock item details for a given SKU.
    """
    base_url = 'https://kosmickitchen.eu/rest/V1'
    encoded_sku = quote(sku, safe='')
    stock_item_url = f"{base_url}/stockItems/{encoded_sku}"
    response = requests.get(stock_item_url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        logging.error(f"Error fetching stock item for SKU {sku}: {response.status_code} - {response.text}")
        return {}

def get_parent_sku_from_db(table: str, child_sku: str) -> str | None:
    """
    Look up the parent_sku for a given child SKU in the specified table.
    Returns the parent_sku string, or None if not found or empty.
    """
    if table not in ALLOWED_TABLES:
        return None

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"SELECT parent_sku FROM {table} WHERE magento_sku = ? AND parent_sku IS NOT NULL",
        (child_sku,)
    )
    row = cur.fetchone()
    conn.close()

    return row["parent_sku"] if row and row["parent_sku"] != child_sku and row["parent_sku"] != 'None' else None

def trigger_parent_product_save(parent_sku: str, headers: dict, table, ensure_in_stock: bool = False) -> tuple:
    """
    Trigger a minimal "save" on the parent configurable product by updating a non-critical field.
    Optionally, when ensure_in_stock=True, also mark the parent stock item as in stock via the legacy
    stock endpoint without changing its qty.
    Returns (ok: bool, message: str). "ok" reflects the minimal save result; the optional stock flip
    logs errors but does not affect the ok flag.
    """
    base_url = 'https://kosmickitchen.eu/rest/V1'
    product_url = f"{base_url}/products/{quote(parent_sku, safe='')}"

    # Fetch current status (or any other simple field)
    resp = requests.get(product_url, headers=headers)
    if resp.status_code != 200:
        return (False, f"Failed to fetch parent product data for SKU '{parent_sku}': "
                       f"{resp.status_code} – {resp.text}")

    product_data = resp.json()

    # Only update the status field with its current value (no risk of missing required attrs)
    payload = {"product": {"sku": parent_sku, "status": product_data.get("status", 1)}}
    update_resp = requests.put(product_url, headers=headers, json=payload)

    if update_resp.status_code not in (200, 204):
        return (False, f"Failed to save parent SKU '{parent_sku}': "
                       f"{update_resp.status_code} – {update_resp.text}")

    # Optionally ensure the parent is marked as in stock (do not alter qty)
    if ensure_in_stock:
        try:
            stock_item = get_stock_item(parent_sku, headers)
            stock_item_id = stock_item.get('item_id') if isinstance(stock_item, dict) else None
            if not stock_item_id:
                logging.error(f"Parent in-stock flip skipped; no stock item for parent SKU {parent_sku}.")
            else:
                parent_qty = stock_item.get('qty', 0)
                update_url = f"{base_url}/products/{quote(parent_sku, safe='')}/stockItems/{stock_item_id}"
                stock_data = {
                    "stockItem": {
                        "qty": parent_qty,
                        "is_in_stock": True,
                        "manage_stock": True,
                        "use_config_manage_stock": True,
                        "min_qty": 0,
                        "min_sale_qty": 1,
                        "max_sale_qty": 10000,
                        "notify_stock_qty": 1
                    }
                }
                s_resp = requests.put(update_url, headers=headers, json=stock_data)
                if s_resp.status_code in (200, 204):
                    logging.info(f"Parent SKU '{parent_sku}' marked in stock (qty preserved: {parent_qty}).")
                else:
                    logging.error(f"Failed to mark parent SKU '{parent_sku}' in stock: {s_resp.status_code} – {s_resp.text}")
        except Exception as e:
            logging.error(f"Exception while marking parent '{parent_sku}' in stock: {e}")

    return (True, f"Parent SKU '{parent_sku}' saved successfully (minimal update){' and in-stock ensured' if ensure_in_stock else ''}.")

def update_stock_item(table: str, sku: str, qty: float, headers: dict, stock_item: dict = None) -> tuple:
    """
    1) Updates the legacy stock item for `sku`
    2) If a parent_sku is set in your local DB for this table/sku, triggers a save on that parent
    3) Flushes the page cache so the frontend shows the updated stock
    """
    if table not in ALLOWED_TABLES:
        return False, f"Invalid table '{table}'"

    # --- 1) Legacy Stock Update (unchanged) ---
    base_url = 'https://kosmickitchen.eu/rest/V1'
    if stock_item is None:
        stock_item = get_stock_item(sku, headers)
    if not stock_item:
        return False, f"Could not fetch current Magento stock item for SKU {sku}; aborting update."

    stock_item_id = stock_item.get('item_id')
    if not stock_item_id:
        return False, f"No stock item ID found for SKU {sku}."

    update_url = f"{base_url}/products/{quote(sku, safe='')}/stockItems/{stock_item_id}"
    stock_data = {
        "stockItem": {
            "qty": qty,
            "is_in_stock": qty > 0,
            "manage_stock": True,
            "use_config_manage_stock": True,
            "min_qty": 0,
            "min_sale_qty": 1,
            "max_sale_qty": 10000,
            "notify_stock_qty": 1
        }
    }
    resp = requests.put(update_url, headers=headers, json=stock_data)
    if resp.status_code != 200:
        return False, f"Failed to update legacy stock for SKU {sku}: {resp.status_code} - {resp.text}"

    # --- 2) Trigger Parent Save if mapped ---
    parent_sku = get_parent_sku_from_db(table, sku)
    if parent_sku:
        ok, msg = trigger_parent_product_save(parent_sku, headers, table, ensure_in_stock=(qty > 0))
        if not ok:
            # log but don’t abort—frontend stock will at least reflect real child state
            logging.error(f"Parent save failed for {parent_sku}: {msg}")

    return True, "Stock updated" + (", parent touched" if parent_sku else "") + ", cache flushed"

def get_magento_product(sku: str, headers: dict) -> dict:
    """
    Fetch full Magento product for a given SKU (global scope).
    """
    base_url = 'https://kosmickitchen.eu/rest/V1'
    product_url = f"{base_url}/products/{quote(sku, safe='')}"
    resp = requests.get(product_url, headers=headers)
    if resp.status_code == 200:
        return resp.json()
    logging.error(f"Error fetching product for SKU {sku}: {resp.status_code} - {resp.text}")
    return {}

def _get_custom_attr(prod: dict, code: str):
    attrs = (prod or {}).get('custom_attributes', [])
    for a in attrs:
        if a.get('attribute_code') == code:
            return a.get('value')
    return None

def _set_special_price_payload(sku: str, value_or_none) -> dict:
    """
    Build a Magento product payload to set or clear special price (and dates when clearing).
    If value_or_none is None, clears special_price, special_from_date, special_to_date.
    Else sets special_price to a string with two decimals.
    """
    if value_or_none is None:
        # Clearing special price in Magento should use JSON null, not empty strings.
        # Also clear date fields to fully remove promotions.
        return {
            "product": {
                "sku": sku,
                "custom_attributes": [
                    {"attribute_code": "special_price", "value": None},
                    {"attribute_code": "special_from_date", "value": None},
                    {"attribute_code": "special_to_date", "value": None}
                ]
            }
        }
    else:
        return {
            "product": {
                "sku": sku,
                "custom_attributes": [
                    {"attribute_code": "special_price", "value": f"{float(value_or_none):.2f}"}
                ]
            }
        }

def _put_magento_product(sku: str, payload: dict, headers: dict) -> tuple[bool, str]:
    base_url = 'https://kosmickitchen.eu/rest/V1'
    product_url = f"{base_url}/products/{quote(sku, safe='')}"
    resp = requests.put(product_url, headers=headers, json=payload)
    if resp.status_code in (200, 201):
        return True, "OK"
    return False, f"{resp.status_code} - {resp.text}"

def sync_stock_with_magento(table: str, product_id: int, new_stock: int) -> None:
    # Re-read the product from the DB.
    conn = get_db_connection()
    try:
        cursor = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        if not row:
            logging.error(f"Product with id {product_id} not found in table {table}.")
            return
        product = dict(row)
    finally:
        conn.close()
    
    magento_sku = product.get("magento_sku", "")
    variation_attr_per_table = {
        'growkits': 'size',
        'cannabis_seeds': 'pack_size',
        'spores': 'form',
        'misc': None
    }
    variation_attr = variation_attr_per_table.get(table, None)
    variation_str = f'{variation_attr}: {product.get(variation_attr)}' if variation_attr else ''
    manufacturer = product.get('manufacturer', '')
    if not magento_sku or magento_sku.lower() == "none":
        logging.info(f"Product '{product.get('name')}' Manufacturer: {manufacturer} {variation_str} (ID: {product_id}) does not have a valid Magento SKU; skipping Magento update.")
        return
    
    # Fetch the current stock item
    headers = stock_app_proposed_order_data_fetcher.headers
    magento_sku = magento_sku.strip()
    stock_item = get_stock_item(magento_sku, headers)
    if not stock_item:
        logging.error(f"Could not fetch current Magento stock item for SKU {magento_sku}; aborting update.")
        return
    m_qty = stock_item.get('qty', 0)
    m_in_stock = stock_item.get('is_in_stock', False)
    if new_stock > 0 and (not m_in_stock or m_qty <= 999):
        qty = 9999
        logging.info(f"Product '{product.get('name')}' (SKU: {magento_sku}) was put in stock (new stock: {new_stock}); updating Magento to in stock with qty {qty}.")

        # Update Magento using the pre-fetched stock_item.
        success, message = update_stock_item(table,magento_sku, qty, headers, stock_item=stock_item)
        if success:
            logging.info(f"Magento stock update succeeded for SKU {magento_sku}.")
        else:
            logging.error(f"Magento stock update FAILED for SKU {magento_sku}: {message}")

    elif new_stock == 0 and (m_in_stock or m_qty > 0):
        qty = 0
        logging.info(f"Product '{product.get('name')}' (SKU: {magento_sku}) is now out of stock (new stock: {new_stock}); updating Magento to out of stock.")
    
        # Update Magento using the pre-fetched stock_item.
        success, message = update_stock_item(table,magento_sku, qty, headers, stock_item=stock_item)
        if success:
            logging.info(f"Magento stock update succeeded for SKU {magento_sku}.")
        else:
            logging.error(f"Magento stock update FAILED for SKU {magento_sku}: {message}")

def async_sync_stock_with_magento(table: str, product_id: int, new_stock: int) -> None:
    """
    Submits sync_stock_with_magento to run in a separate thread.
    """
    def task():
        try:
            sync_stock_with_magento(table, product_id, new_stock)
        except Exception as e:
            logging.error(f"Exception in sync_stock_with_magento for product {product_id}: {str(e)}")
    t = threading.Thread(target=task)
    t.start()

def sync_special_price_with_magento(table: str, product_id: int, magento_sku: str, special_price) -> None:
    """
    Sync special price to Magento for the given product.
    If special_price is None, remove the special price from Magento.
    Clears special_from_date/special_to_date when removing.
    """
    if not magento_sku or magento_sku.lower() == "none":
        logging.info(f"Product ID {product_id} does not have a valid Magento SKU; skipping special price sync.")
        return

    # Context for logging
    product_name = None
    try:
        with get_db_connection() as conn:
            row = conn.execute(f"SELECT name FROM {table} WHERE id = ?", (product_id,)).fetchone()
            if row:
                product_name = row['name'] if 'name' in row.keys() else None
    except Exception:
        pass

    sku = magento_sku.strip()
    headers = stock_app_proposed_order_data_fetcher.headers

    m_product = get_magento_product(sku, headers)
    if not m_product:
        logging.error(f"Could not fetch Magento product for SKU {sku}; aborting special price sync.")
        return

    current_sp = _get_custom_attr(m_product, 'special_price')  # string or None

    def _equals(a, b) -> bool:
        try:
            if a is None and b is None:
                return True
            if a is None or b is None:
                return False
            return abs(float(a) - float(b)) < 0.005
        except Exception:
            return False

    if special_price is None:
        # Remove if present; also clear date fields
        if (current_sp is None) or (str(current_sp).strip() == ""):
            # No actual change on Magento; skip parent touch
            logging.info(f"No-op: Magento already has no special price for SKU {sku}.")
            return
        else:
            payload = _set_special_price_payload(sku, None)
            ok, msg = _put_magento_product(sku, payload, headers)
            if ok:
                logging.info(f"Magento special price REMOVED for SKU {sku} (Product: {product_name or product_id}, Table: {table}).")
                # Touch parent ONLY when child change succeeded
                parent_sku = get_parent_sku_from_db(table, sku)
                if parent_sku:
                    ok2, msg2 = trigger_parent_product_save(parent_sku, headers, table)
                    if not ok2:
                        logging.error(f"Parent save failed for {parent_sku} after special price removal: {msg2}")
            else:
                logging.error(f"Magento special price removal FAILED for SKU {sku}: {msg}")
            return

    try:
        sp_val = float(special_price)
    except (ValueError, TypeError):
        logging.error(f"Invalid special price value for SKU {sku}: {special_price}")
        return

    if _equals(current_sp, sp_val):
        logging.info(f"No-op: Magento special price already {float(current_sp):.2f} for SKU {sku}.")
        return

    payload = _set_special_price_payload(sku, sp_val)
    ok, msg = _put_magento_product(sku, payload, headers)
    if ok:
        logging.info(f"Magento special price UPDATED for SKU {sku}: {current_sp} -> {sp_val:.2f} (Product: {product_name or product_id}, Table: {table}).")
        # Touch parent ONLY when child change succeeded
        parent_sku = get_parent_sku_from_db(table, sku)
        if parent_sku:
            ok2, msg2 = trigger_parent_product_save(parent_sku, headers, table)
            if not ok2:
                logging.error(f"Parent save failed for {parent_sku} after special price update: {msg2}")
    else:
        logging.error(f"Magento special price update FAILED for SKU {sku}: {msg}")

def async_sync_special_price_to_magento(table: str, product_id: int, magento_sku: str, special_price) -> None:
    """
    Submits sync_special_price_with_magento to run in a separate thread.
    """
    def task():
        try:
            sync_special_price_with_magento(table, product_id, magento_sku, special_price)
        except Exception as e:
            logging.error(f"Exception in sync_special_price_with_magento for product {product_id}: {str(e)}")
    t = threading.Thread(target=task)
    t.start()

@app.route('/check_product_stock/<sku>/<int:qty_needed>', methods=['GET'])
def api_check_product_stock(sku, qty_needed):
    """
    Check if a product with given SKU has at least qty_needed in stock.
    Returns: {in_stock: bool, name, current_stock, qty_needed}
    """
    for table in query_table.keys():
        with get_db_connection() as conn:
            if table == "cannabis_seeds":
                cursor = conn.execute(
                    f"SELECT stock, name, storage_location_number FROM cannabis_seeds WHERE magento_sku = ?",
                    (sku,)
                )
            else:
                cursor = conn.execute(
                    f"SELECT stock, name FROM {table} WHERE magento_sku = ?",
                    (sku,)
                )
            row = cursor.fetchone()
            if row:
                current_stock = row['stock']
                product_name = row['name']
                storage_location_number = row['storage_location_number'] if table == "cannabis_seeds" else None
                if current_stock < qty_needed:
                    return jsonify({
                        "in_stock": False,
                        "name": product_name,
                        "current_stock": current_stock,
                        "qty_needed": qty_needed,
                        "storage_location_number": storage_location_number
                    })
                return jsonify({
                    "in_stock": True,
                    "name": product_name,
                    "current_stock": current_stock,
                    "qty_needed": qty_needed,
                    "storage_location_number": storage_location_number
                })
    return jsonify({"in_stock": True, "name": None, "current_stock": None, "qty_needed": None, "storage_location_number": None})

@app.route('/order_has_stocked_products', methods=['POST'])
def api_order_has_stocked_products():
    """
    Check if any SKUs in the list exist in the stock DB.
    Expects: JSON { "skus": [ ... ] }
    Returns: { "has_stocked_products": bool }
    """
    data = request.get_json()
    skus = data.get("skus", [])
    for table in query_table.keys():
        with get_db_connection() as conn:
            try:
                cursor = conn.execute(
                    f"SELECT 1 FROM {table} WHERE magento_sku IN ({','.join(['?']*len(skus))}) LIMIT 1",
                    skus
                )
                if cursor.fetchone():
                    return jsonify({"has_stocked_products": True})
            except Exception as e:
                print(f"ERROR: Error querying table {table} for SKUs {skus}: {e}")

    return jsonify({"has_stocked_products": False})

@app.route('/batch_order_has_stocked_products', methods=['POST'])
def api_batch_order_has_stocked_products():
    """
    Batch check if any SKUs exist in the stock DB by looping over query_table.keys().
    Expects: JSON { "skus": [ ... ] }
    Returns: { "has_stocked_products": bool }
    """
    data = request.get_json()
    skus = data.get("skus", [])

    for table in query_table.keys():
        with get_db_connection() as conn:
            try:
                cursor = conn.execute(
                    f"SELECT 1 FROM {table} WHERE magento_sku IN ({','.join(['?']*len(skus))}) LIMIT 1",
                    skus
                )
                if cursor.fetchone():
                    return jsonify({"has_stocked_products": True})
            except Exception as e:
                print(f"ERROR: Error querying table {table} for SKUs {skus}: {e}")

    print(f"INFO: No SKUs found in any table: {skus}")
    return jsonify({"has_stocked_products": False})

@app.route('/batch_check_order_stock', methods=['POST'])
def api_batch_check_order_stock():
    """
    Batch check stock availability for a set of SKUs across all tables.
    Expects: JSON { "skus": [ ... ] }
    Returns: { "stock_availability": { sku: bool, ... } }
    """
    data = request.get_json()
    skus = data.get("skus", [])
    stock_availability = {sku: False for sku in skus}
    for table in query_table.keys():
        with get_db_connection() as conn:
            cursor = conn.execute(
                f"SELECT magento_sku, stock FROM {table} WHERE magento_sku IN ({','.join(['?']*len(skus))})",
                skus
            )
            for row in cursor.fetchall():
                sku = row['magento_sku']
                stock_qty = row['stock']
                if stock_qty > 0:
                    stock_availability[sku] = True
    return jsonify({"stock_availability": stock_availability})

# API route: /skus_per_manufacturer
@app.route('/skus_per_manufacturer', methods=["GET"])
def skus_per_manufacturer():
    table = request.args.get("table", "growkits")
    if table not in ALLOWED_TABLES:
        return jsonify({"error": "Invalid table specified."}), 400
    result = {}
    with get_db_connection() as conn:
        cursor = conn.execute(f"SELECT manufacturer, magento_sku FROM {table}")
        for row in cursor.fetchall():
            manufacturer = row[0]
            sku = row[1]
            if manufacturer not in result:
                result[manufacturer] = set()
            if sku:
                result[manufacturer].add(sku)
    # Convert sets to lists for JSON serialization
    result = {k: list(v) for k, v in result.items()}
    return jsonify(result)


# API: fetch products for a given table + manufacturer
@app.route('/fetch_products', methods=["GET"])
def api_fetch_products():
    table = request.args.get('table')
    manufacturer = request.args.get('manufacturer', '')
    if not table or table not in ALLOWED_TABLES:
        return jsonify({"error": "invalid or missing table"}), 400
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(f"SELECT * FROM {table} WHERE manufacturer = ?", (manufacturer,))
            rows = cursor.fetchall()
            items = [dict(r) for r in rows]
        return jsonify({"items": items}), 200
    except Exception as e:
        logging.exception("Failed to fetch products for table %s manufacturer %s", table, manufacturer)
        return jsonify({"error": str(e)}), 500

def get_distinct_manufacturers():
    all_manufacturers = set()
    with get_db_connection() as conn:
        for table in ALLOWED_TABLES:
            try:
                cur = conn.execute(f"SELECT DISTINCT manufacturer FROM {table}")
                all_manufacturers.update(row[0] for row in cur.fetchall() if row[0])
            except Exception:
                continue
    # all_manufacturers.discard('None')
    return all_manufacturers

@app.route('/sync/prices', methods=["GET", "POST"])
def sync_prices_page():
    """
    Admin page to dry-run and apply base/special price syncs to Magento.
    Minimal gating; intended for local use.
    """
    allowed_tables = sorted(ALLOWED_TABLES)
    form = {
        'include_base': True,
        'include_special': False,
        'only_flagged': True,
        'table': '',
        'manufacturer': '',
        'dry_run': True,
    }

    changes = []
    results_map = {}
    summary = None

    if request.method == 'POST':
        include_base = '1' in request.form.getlist('include_base')
        include_special = '1' in request.form.getlist('include_special')
        only_flagged = '1' in request.form.getlist('only_flagged')
        table = request.form.get('table', '').strip()
        manufacturer = request.form.get('manufacturer', '').strip()
        dry_run = '1' in request.form.getlist('dry_run') and 'apply' not in request.form

        form.update({
            'include_base': include_base,
            'include_special': include_special,
            'only_flagged': only_flagged,
            'table': table,
            'manufacturer': manufacturer,
            'dry_run': dry_run,
        })

        try:
            products = stock_app_magento_sync.list_products(db, allowed_tables, table or None, manufacturer or None)
            # Optimization: if only syncing special prices with only-flagged selected, and base sync is off,
            # limit the product list to flagged rows to reduce Magento fetch volume.
            if include_special and only_flagged and not include_base:
                products = [p for p in products if int(p.get('sync_special_price_to_magento') or 0) == 1]
            skus = [p['magento_sku'] for p in products]
            client = stock_app_magento_sync.MagentoClient('https://kosmickitchen.eu/rest/V1', stock_app_proposed_order_data_fetcher.headers)
            magento_map = stock_app_magento_sync.fetch_magento_map(client, skus)

            base_changes = stock_app_magento_sync.diff_base_price(products, magento_map) if include_base else []
            special_changes = stock_app_magento_sync.diff_special_price(products, magento_map, only_flagged=only_flagged) if include_special else []
            changes = base_changes + special_changes

            summary = {
                'base_count': len(base_changes),
                'special_count': len(special_changes),
            }

            # Apply changes when requested (non-dry-run submit with apply)
            if 'apply' in request.form and changes:
                # If a cached changes payload was posted, prefer it for exact reproducibility
                cached_json = request.form.get('cached_changes')
                if cached_json:
                    try:
                        import json
                        changes = json.loads(cached_json)
                    except Exception:
                        pass
                apply_results = stock_app_magento_sync.apply_changes(client, changes)
                # Build a quick lookup map for template
                for r in apply_results:
                    results_map[f"{r['sku']}|{r['kind']}"] = r

                # Log summary for applied updates (no logging for dry-run)
                # Count successes per kind
                base_applied = [r for r in apply_results if r.get('kind') == 'base']
                special_applied = [r for r in apply_results if r.get('kind') == 'special']
                base_updated = sum(1 for r in base_applied if r.get('ok'))
                special_updated = sum(1 for r in special_applied if r.get('ok'))

                table_label = table or 'ALL'
                manufacturer_label = manufacturer or 'ALL'
                if include_base:
                    logging.info(
                        f"Sync Prices Applied — table: {table_label}, manufacturer: {manufacturer_label}, kind: base, only_flagged: {only_flagged}, updated: {base_updated}"
                    )
                if include_special:
                    logging.info(
                        f"Sync Prices Applied — table: {table_label}, manufacturer: {manufacturer_label}, kind: special, only_flagged: {only_flagged}, updated: {special_updated}"
                    )
        except Exception as e:
            logging.exception(
                "Sync/prices error — table: %s, manufacturer: %s, include_base: %s, include_special: %s, only_flagged: %s, apply: %s",
                table or 'ALL', manufacturer or 'ALL', include_base, include_special, only_flagged, ('apply' in request.form)
            )

    return render_template(
        'sync_prices.html',
        allowed_tables=allowed_tables,
        all_manufacturers=sorted(get_distinct_manufacturers()),
        form=form,
        changes=changes,
        results=results_map,
        summary=summary,
    )

@app.route('/toggle_specials', methods=['GET'])
def toggle_specials():
    """
    Toggle the cookie that controls visibility of special prices and
    redirect back to the provided 'next' URL or Referer.
    """
    current = request.cookies.get('show_special_prices', '1')
    new_val = '0' if current == '1' else '1'
    # Validate next path to avoid open redirects: only allow relative paths
    next_url = request.args.get('next') or request.headers.get('Referer') or '/'
    try:
        # Only accept paths starting with a single '/'
        if not (isinstance(next_url, str) and next_url.startswith('/') and not next_url.startswith('//')):
            next_url = '/'
    except Exception:
        next_url = '/'

    resp = redirect(next_url)
    # Persist for a year
    resp.set_cookie('show_special_prices', new_val, max_age=60*60*24*365, samesite='Lax')
    return resp

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok"}), 200

def main():
    hostname = socket.gethostname()
    ipv4_address = socket.gethostbyname(hostname)
    print(f'Stock App\n\nrunning on http://{ipv4_address}:{stock_app_port}/\n')
    webbrowser.open(f'http://{ipv4_address}:{stock_app_port}/', new=2)
    serve(app, host=f'{ipv4_address}', port=stock_app_port, threads=20)
    # app.run(debug=True)

if __name__ == '__main__':
    main()