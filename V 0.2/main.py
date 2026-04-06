import json
import mysql.connector
import api

def solicitar_numero(mensaje, tipo='int'):
    while True:
        try:
            valor = input(mensaje)
            if tipo == 'float':
                return float(valor)
            return int(valor)
        except ValueError:
            print(f'\n ERROR: "{valor}" no es un número válido.')

contador = 0

while True:
    
    if contador == 0: 
        print('   SISTEMA CORESTACK - INICIO') 
    else: 
        print('   SISTEMA CORESTACK - PANEL')

    opcion = input('\nMenú Principal:\n1. Productos\n2. Proveedores\n3. Ventas\n0. Salir\n\nSeleccione una opción: ')
    contador += 1

    try:
        match opcion:
            case '1':
                print('\n GESTIÓN DE PRODUCTOS')
                producto_opc = input('1. Buscar productos\n2. Agregar mercadería\n3. Eliminar mercadería\nSeleccione: ')

                match producto_opc:
                    case '1':
                        print('\n BUSCAR PRODUCTOS')
                        buscador_contador = solicitar_numero('¿Cuántos productos va a buscar?: ')

                        while buscador_contador > 0:
                            product = input('\nNombre del producto: ').title()
                            datos = api.view_products(product)
                            buscador_contador -= 1

                            if datos:
                                print(f'Datos encontrados: {datos}')
                            else:
                                print(f'ERROR: No existen datos para {product}')

                    case '2':
                        print('\n AÑADIR MERCADERÍA')
                        buscador_contador = solicitar_numero('¿Cuántos productos va a añadir?: ')

                        while buscador_contador > 0:
                            product = input('\nNombre del producto: ').title()
                            category = input(f'Categoría de {product}: ').title()
                            price = solicitar_numero(f'Precio de {product}: ', tipo='float')
                            quantity = solicitar_numero(f'Stock inicial de {product}: ')
                            
                            api.add_products(product, category, price, quantity)
                            print(f'{product} añadido correctamente.')
                            buscador_contador -= 1

                    case '3':
                        print('\nELIMINAR PRODUCTOS')
                        buscador_contador = solicitar_numero('¿Cuántos productos desea eliminar?: ')

                        while buscador_contador > 0:
                            product = input('\nNombre del producto a eliminar: ').title()
                            confirmacion = input(f"¿Seguro que desea eliminar {product}? (S/N): ").upper()
                            
                            if confirmacion == 'S':
                                api.delete_products(product)
                                print(f'Operación finalizada para {product}.')
                            else:
                                print(f'Eliminación cancelada para {product}.')
                            
                            buscador_contador -= 1

            case '2':
                print('\n GESTIÓN DE PROVEEDORES')
                proveedor_opc = input('1. Buscar proveedor\n2. Agregar proveedor\n3. Eliminar proveedor\nSeleccione: ')

                match proveedor_opc:
                    case '1':
                        print('\nBUSCAR PROVEEDORES')
                        buscador_contador = solicitar_numero('¿Cuántos va a buscar?: ')

                        while buscador_contador > 0:
                            supplier = input('\nNombre del proveedor: ')
                            datos = api.search_suppliers(supplier)
                            
                            if datos:
                                print(f'Datos: {datos}')
                                buscador_contador -= 1
                            else:
                                print(f'ERROR: No se encontró a {supplier}')

                    case '2':
                        print('\n AGREGAR PROVEEDOR')
                        buscador_contador = solicitar_numero('¿Cuántos va a añadir?: ')

                        while buscador_contador > 0:
                            supplier = input('\nNombre del proveedor: ').title()
                            city = input(f'Ciudad de {supplier}: ').title()
                            mail = input(f'Email de {supplier}: ')
                            tel = solicitar_numero(f'Teléfono de {supplier}: ')

                            api.add_suppliers(supplier, city, mail, tel)
                            print(f'Proveedor {supplier} registrado.')
                            buscador_contador -= 1

                    case '3':
                        print('\n ELIMINAR PROVEEDOR')
                        buscador_contador = solicitar_numero('¿Cuántos desea eliminar?: ')

                        while buscador_contador > 0:
                            supplier = input('\nNombre del proveedor a borrar: ').title()
                            api.delete_suppliers(supplier)
                            print(f' Operación finalizada para {supplier}.')
                            buscador_contador -= 1

            case '3':
                print('\n MÓDULO DE VENTAS')
                ventas_opc = input('1. Registrar venta\n2. Ver ventas \nSeleccione: ')
                
                match ventas_opc:

                    case '1':
                        cant_ventas = solicitar_numero('\n¿Cuántas ventas desea registrar?: ')
                        
                        while cant_ventas > 0:
                            product = input('\n Producto vendido: ').title()
                            product_exists = api.search_products(product)

                            if product_exists is None:
                                print(f'ERROR: {product} no existe. Debe cargarlo en Productos primero.')
                                continue

                            payment_type = input('Método de pago: ')
                            quantity = solicitar_numero('Cantidad: ')
                            v_quantity = api.verificate_products_quantity(product)
                            
                            if quantity > v_quantity:
                                print(f'ERROR: Stock insuficiente. Solo hay {v_quantity} unidades.')
                                continue

                            total_amount = api.select_price_product(product, quantity)
                            api.add_sell(payment_type, quantity, total_amount, product)
                            api.rest_quantity_products(product, quantity)

                            print(f'VENTA EXITOSA: Total a cobrar ${total_amount}')
                            cant_ventas -= 1

                    case '2':
                        print('\n HISTORIAL DE VENTAS')
                        print(api.show_sells())

            case '0':
                print('Saliendo del sistema')
                break

    except mysql.connector.Error as error:
        print(f"\nERROR: Falla con conexion en la Base de Datos: {error}")
    except Exception as e:
        print(f"\nOcurrió un error inesperado: {e}")