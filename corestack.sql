-- Base de datos: `corestack`
--

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `products`
--

CREATE TABLE `products` (
  `idProduct` int(11) NOT NULL,
  `product` varchar(100) NOT NULL,
  `category` enum('Dulces','Salados','Agridulces') NOT NULL,
  `price` float NOT NULL,
  `stock` int(11) NOT NULL,
  `idSupplier` int(11) DEFAULT NULL,
  `añadido_el` timestamp NOT NULL DEFAULT current_timestamp(),
  `active` tinyint(1) DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `products`
--

INSERT INTO `products` (`idProduct`, `product`, `category`, `price`, `stock`, `idSupplier`, `añadido_el`, `active`) VALUES
(1, 'Coca Cola 500ml', 'Salados', 1500, 50, 1, '2026-03-27 16:31:30', 1),
(2, 'Agua Villavicencio', 'Salados', 800, 100, 1, '2026-03-27 16:31:30', 1),
(3, 'Alfa Guaymallen', 'Dulces', 600, 200, 2, '2026-03-27 16:31:30', 1),
(4, 'Mogul Confitado', 'Dulces', 1200, 80, 2, '2026-03-27 16:31:30', 1),
(5, 'Bon o Bon', 'Dulces', 400, 137, 2, '2026-03-27 16:31:30', 1),
(6, 'Pan Lactal Bimbo', 'Salados', 2500, 20, 3, '2026-03-27 16:31:30', 1),
(7, 'Mantecol 250g', 'Dulces', 1800, 40, 4, '2026-03-27 16:31:30', 1),
(8, 'Oreo Original', 'Dulces', 1300, 60, 4, '2026-03-27 16:31:30', 1),
(9, 'Cereal Mix', 'Agridulces', 900, 25, 2, '2026-03-27 16:31:30', 0),
(10, 'Papas Lays', 'Salados', 2200, 25, 5, '2026-03-27 16:31:30', 1),
(12, 'Papas Blancas', 'Salados', 100, 10000, NULL, '2026-03-29 23:00:31', 1);

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `products_sells`
--

CREATE TABLE `products_sells` (
  `idProduct_sell` int(11) NOT NULL,
  `idSell` int(11) NOT NULL,
  `idProduct` int(11) NOT NULL,
  `cantidad_vendida` int(11) NOT NULL,
  `subtotal` float NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `products_sells`
--

INSERT INTO `products_sells` (`idProduct_sell`, `idSell`, `idProduct`, `cantidad_vendida`, `subtotal`) VALUES
(1, 1, 1, 1, 1500),
(2, 1, 3, 1, 600),
(3, 2, 6, 1, 2500),
(4, 2, 9, 1, 1000),
(5, 3, 8, 1, 1300);

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `sells`
--

CREATE TABLE `sells` (
  `idSell` int(11) NOT NULL,
  `payment_type` varchar(100) DEFAULT NULL,
  `total_amount` decimal(10,2) DEFAULT NULL,
  `quantity` int(11) NOT NULL,
  `created_at` datetime DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `sells`
--

INSERT INTO `sells` (`idSell`, `payment_type`, `total_amount`, `quantity`, `created_at`) VALUES
(1, 'Efectivo', 2100.00, 10, '2026-03-27 13:31:30'),
(2, 'Billetera Virtual', 3500.00, 2, '2026-03-27 13:31:30'),
(3, 'Debito', 1300.00, 94, '2026-03-27 13:31:30'),
(4, 'Efectivo', 2000.00, 44, NULL),
(5, 'efectivo', 0.00, 3, NULL),
(6, 'efectivo', 7600.00, 19, NULL),
(7, 'Efectivo', 59600.00, 149, NULL),
(8, 'efectivo', 8000.00, 20, NULL),
(9, 'efectivo', 5200.00, 13, NULL),
(10, 'efectivo', 800.00, 2, NULL),
(11, 'efectivo', 1800.00, 2, NULL),
(12, 'efectivo', 1200.00, 3, NULL),
(13, 'efectivo', 900.00, 1, '2026-03-30 11:51:56'),
(14, 'efectivo', 1800.00, 2, '2026-03-30 12:28:14');

-- --------------------------------------------------------

--
-- Estructura de tabla para la tabla `suppliers`
--

CREATE TABLE `suppliers` (
  `idSupplier` int(11) NOT NULL,
  `supplier` varchar(250) NOT NULL,
  `city` varchar(200) DEFAULT NULL,
  `mail` varchar(100) DEFAULT NULL,
  `tel` varchar(20) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Volcado de datos para la tabla `suppliers`
--

INSERT INTO `suppliers` (`idSupplier`, `supplier`, `city`, `mail`, `tel`) VALUES
(1, 'Femsa Argentina', 'CABA', 'ventas@femsa.com.ar', '1144556677'),
(2, 'Arcor SA', 'Cordoba', 'mayorista@arcor.com', '0351-445566'),
(3, 'Bimbo SRL', 'Pilar', 'pedidos@bimbo.com', '1122334455'),
(4, 'Mondelez IT', 'General Pacheco', 'soporte@mondelez.com', '1166778899'),
(5, 'Distribuidora Alsina', 'Lanus', 'alsina@distri.com', '1133221100');

--
-- Índices para tablas volcadas
--

--
-- Indices de la tabla `products`
--
ALTER TABLE `products`
  ADD PRIMARY KEY (`idProduct`),
  ADD KEY `idSupplier` (`idSupplier`);

--
-- Indices de la tabla `products_sells`
--
ALTER TABLE `products_sells`
  ADD PRIMARY KEY (`idProduct_sell`),
  ADD KEY `idSell` (`idSell`),
  ADD KEY `idProduct` (`idProduct`);

--
-- Indices de la tabla `sells`
--
ALTER TABLE `sells`
  ADD PRIMARY KEY (`idSell`);

--
-- Indices de la tabla `suppliers`
--
ALTER TABLE `suppliers`
  ADD PRIMARY KEY (`idSupplier`);

--
-- AUTO_INCREMENT de las tablas volcadas
--

--
-- AUTO_INCREMENT de la tabla `products`
--
ALTER TABLE `products`
  MODIFY `idProduct` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=13;

--
-- AUTO_INCREMENT de la tabla `products_sells`
--
ALTER TABLE `products_sells`
  MODIFY `idProduct_sell` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=6;

--
-- AUTO_INCREMENT de la tabla `sells`
--
ALTER TABLE `sells`
  MODIFY `idSell` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=15;

--
-- AUTO_INCREMENT de la tabla `suppliers`
--
ALTER TABLE `suppliers`
  MODIFY `idSupplier` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=7;

--
-- Restricciones para tablas volcadas
--

--
-- Filtros para la tabla `products`
--
ALTER TABLE `products`
  ADD CONSTRAINT `products_ibfk_1` FOREIGN KEY (`idSupplier`) REFERENCES `suppliers` (`idSupplier`);

--
-- Filtros para la tabla `products_sells`
--
ALTER TABLE `products_sells`
  ADD CONSTRAINT `products_sells_ibfk_1` FOREIGN KEY (`idSell`) REFERENCES `sells` (`idSell`),
  ADD CONSTRAINT `products_sells_ibfk_2` FOREIGN KEY (`idProduct`) REFERENCES `products` (`idProduct`);
COMMIT;