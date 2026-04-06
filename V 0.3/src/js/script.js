let datosGuardados = localStorage.getItem("productos_inventario");
let products = [];

if (datosGuardados == null) {
    products = [
        { id: 1, name: "Café Molido", price: 4500, stock: 25, supplier: "Nestlé", date: "06/04/2026" },
        { id: 2, name: "Yerba Mate 1kg", price: 3200, stock: 40, supplier: "Taragüí", date: "06/04/2026" }
    ];
} else {
    // Si hay, los transformamos en objeto
    products = JSON.parse(datosGuardados);
}

function saveToLocalStorage() {
    let contenido = JSON.stringify(products);
    localStorage.setItem("productos_inventario", contenido);
}

const bodyProducts = document.getElementById("bodyProducts");

// 3. Función para la tabla
function renderProducts() {
    bodyProducts.innerHTML = ""; 
    
    for (let i = 0; i < products.length; i++) {
        let p = products[i];
        let row = document.createElement("tr");
        
        row.innerHTML = "<td>" + p.name + "</td>" +
                        "<td>" + p.id + "</td>" +
                        "<td>$" + p.price + "</td>" +
                        "<td>" + p.stock + "</td>" +
                        "<td>" + p.supplier + "</td>" +
                        "<td>" + p.date + "</td>" +
                        "<td>" +
                            "<button onclick='edit_product(" + i + ")'>Editar</button>" +
                            "<button onclick='delete_product(" + i + ")'>Borrar</button>" +
                        "</td>";
        
        bodyProducts.appendChild(row);
    }
}

// 4. Agregar Producto 
function new_product() {
    let name = prompt("Nombre:");
    let price = prompt("Precio:");
    let stock = prompt("Stock:");
    let supplier = prompt("Proveedor:");

    if (name != "" && price != "") {
        let idNuevo = 1;
        if (products.length > 0) {
            idNuevo = products[products.length - 1].id + 1;
        }

        let nuevoObj = {
            id: idNuevo,
            name: name,
            price: price,
            stock: stock,
            supplier: supplier,
            date: "06/04/2026"
        };

        products.push(nuevoObj);
        saveToLocalStorage();
        renderProducts();
    }
}

function delete_product(index) {
    let pregunta = confirm("¿Seguro que querés borrarlo?");
    if (pregunta == true) {
        products.splice(index, 1);
        saveToLocalStorage();
        renderProducts();
    }
}

function edit_product(index) {
    let nuevoPrecio = prompt("Cual es el nuevo precio?", products[index].price);
    if (nuevoPrecio != null) {
        products[index].price = nuevoPrecio;
        saveToLocalStorage();
        renderProducts();
    }
}

function verProductos() {
    document.getElementById("sectionProducts").style.display = "block";
    document.getElementById("sectionSells").style.display = "none";
    document.getElementById("sectionSuppliers").style.display = "none";
}

function verVentas() {
    document.getElementById("sectionProducts").style.display = "none";
    document.getElementById("sectionSells").style.display = "block";
    document.getElementById("sectionSuppliers").style.display = "none";
}

// No te olvides de llamar a los botones en el HTML con onclick="verProductos()", etc.

renderProducts();