import mysql.connector

# CONEXION Base de datos XAMPP
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="corestack"
)
cursor = db.cursor()

# OPCIONES productos

def show_products():
    sql = "SELECT * FROM products WHERE active = 1"
    cursor.execute(sql)
    resultado = cursor.fetchall()
    return resultado

def delete_products(product):
    sql = "UPDATE products SET active = 0 WHERE product = %s"
    valores = (product,)
    cursor.execute(sql, valores)
    db.commit()

def add_products(product, category, price, quantity):
    sql = "INSERT INTO products(product, category, price, stock) VALUES(%s, %s, %s, %s)"
    valores = (product, category, price, quantity)
    cursor.execute(sql, valores)
    db.commit()

def view_products(product):
    sql = "SELECT * FROM products WHERE product = %s"
    valores = (product,)
    cursor.execute(sql, valores)
    resultado = cursor.fetchone()
    return resultado

def search_products(product):
    sql = "SELECT * FROM products WHERE product = %s AND active = 1"
    valores = (product,)
    cursor.execute(sql, valores)
    resultado = cursor.fetchone()
    return resultado

def select_price_product(product, quantity):
    sql = "SELECT price FROM products WHERE product = %s"
    valores = (product,)
    cursor.execute(sql, valores)
    resultado = cursor.fetchone()
    if resultado:
        precio = resultado[0]
        total_amount = precio * quantity
        return total_amount
    return 0

def verificate_products_quantity(product):
    sql = "SELECT stock FROM products WHERE product = %s"
    valores = (product,)
    cursor.execute(sql, valores)
    resultado = cursor.fetchone()
    if resultado:
        v_quantity = resultado[0]
        return v_quantity
    return 0

def rest_quantity_products(product, quantity):
    sql = "UPDATE products SET stock = stock - %s WHERE product = %s"
    valores = (quantity, product)
    cursor.execute(sql, valores)
    db.commit()

# OPCIONES Proveedores

def show_suppliers():
    sql = "SELECT * FROM suppliers"
    cursor.execute(sql)
    resultado = cursor.fetchall()
    return resultado

def search_suppliers(supplier):
    sql = "SELECT * FROM suppliers WHERE supplier = %s"
    valores = (supplier,)
    cursor.execute(sql, valores)
    resultado = cursor.fetchone()
    return resultado

def add_suppliers(supplier, city, mail, tel):
    sql = "INSERT INTO suppliers(supplier, city, mail, tel) VALUES(%s, %s, %s, %s)"
    valores = (supplier, city, mail, tel)
    cursor.execute(sql, valores)
    db.commit()

def delete_suppliers(supplier):
    sql = "DELETE FROM suppliers WHERE supplier = %s"
    valores = (supplier,)
    cursor.execute(sql, valores)
    db.commit()

# OPCIONES Ventas

def add_sell(payment_type, quantity, total_amount, product_name):
    # 1. Buscamos el ID del producto por su nombre
    sql_id = "SELECT idProduct FROM products WHERE product = %s"
    cursor.execute(sql_id, (product_name,))
    res = cursor.fetchone()
    
    if res:
        id_prod = res[0]
        
        sql_sell = "INSERT INTO sells (payment_type, total_amount, created_at) VALUES (%s, %s, NOW())"
        cursor.execute(sql_sell, (payment_type, total_amount))
        id_venta = cursor.lastrowid # Recuperamos el ID que generó la base de datos
        
        sql_detalle = " INSERT INTO products_sell (idSell, idProduct, cantidad_vendida, subtotal) VALUES (%s, %s, %s, %s)"
        valores_detalle = (id_venta, id_prod, quantity, total_amount)
        cursor.execute(sql_detalle, valores_detalle)
        
        db.commit()

def show_sells():
    sql = "SELECT * FROM sells"
    cursor.execute(sql)
    resultado = cursor.fetchall()
    return resultado