"""Catálogo fictício: segmentos, regiões, produtos e frota.

Todos os nomes são inventados. Nenhum dado se refere a empresas reais.
"""

from __future__ import annotations

from dataclasses import dataclass

COMPANY_NAME = "Nexo Equipamentos (empresa fictícia)"

SEGMENTS = {
    # segmento: (peso na base, prefixos de razão social)
    "Construção": (0.38, ["Construtora", "Engenharia", "Obras"]),
    "Eventos": (0.16, ["Eventos", "Produções", "Palcos"]),
    "Indústria": (0.20, ["Indústria", "Metalúrgica", "Plásticos"]),
    "Agronegócio": (0.14, ["Agropecuária", "Agrícola", "Cerealista"]),
    "Serviços": (0.12, ["Serviços", "Facilities", "Manutenção"]),
}

REGIONS = {
    # região: (peso, [(cidade, UF)], vendedores)
    "Sudeste": (0.42, [("São Paulo", "SP"), ("Campinas", "SP"), ("Belo Horizonte", "MG"),
                       ("Rio de Janeiro", "RJ"), ("Vitória", "ES")], ["V01", "V02", "V03", "V04"]),
    "Sul": (0.22, [("Curitiba", "PR"), ("Porto Alegre", "RS"), ("Joinville", "SC"),
                   ("Londrina", "PR")], ["V05", "V06", "V07"]),
    "Nordeste": (0.16, [("Recife", "PE"), ("Salvador", "BA"), ("Fortaleza", "CE")],
                 ["V08", "V09"]),
    "Centro-Oeste": (0.13, [("Goiânia", "GO"), ("Cuiabá", "MT"), ("Campo Grande", "MS")],
                     ["V10", "V11"]),
    "Norte": (0.07, [("Manaus", "AM"), ("Belém", "PA")], ["V12"]),
}

SYLLABLES = [
    "ba", "ca", "da", "fa", "ga", "la", "ma", "na", "ra", "ta", "va", "xe", "lo", "ri",
    "su", "ne", "to", "qua", "ter", "val", "mar", "cor", "lin", "dor", "gar", "pel",
    "vin", "zu", "bra", "cre", "tri", "ven", "sol", "nor", "ju", "pi", "ro", "le",
]

LEGAL_SUFFIXES = ["Ltda", "Ltda", "Ltda", "S.A.", "ME"]


@dataclass(frozen=True)
class Product:
    sku: str
    description: str
    product_line: str
    unit: str
    sale_price: float | None  # preço de lista de venda (R$/unidade)
    cost_ratio: float | None  # custo direto / preço de lista (venda)
    rental_monthly_rate: float | None  # tabela de locação (R$/unidade/mês)
    unit_acquisition_cost: float | None  # custo de aquisição da unidade física
    fleet_size: int  # unidades físicas no início do período
    target_utilization: float  # utilização-alvo no início da janela (define a demanda)
    sale_weight: float  # peso relativo na venda


PRODUCTS: list[Product] = [
    # Geradores: vendidos e alugados
    Product("GER-030", "Gerador diesel 30 kVA", "Geradores", "un", 58_000, 0.66, 4_200, 52_000, 20, 0.62, 0.40),
    Product("GER-055", "Gerador diesel 55 kVA", "Geradores", "un", 86_000, 0.67, 6_100, 78_000, 22, 0.64, 0.35),
    Product("GER-115", "Gerador diesel 115 kVA", "Geradores", "un", 148_000, 0.68, 9_800, 132_000, 14, 0.60, 0.10),
    Product("GER-260", "Gerador diesel 260 kVA", "Geradores", "un", 265_000, 0.69, 16_500, 238_000, 8, 0.55, 0.02),
    # Plataformas elevatórias: locação
    Product("PLT-T08", "Plataforma tesoura elétrica 8 m", "Plataformas elevatórias", "un", None, None, 3_900, 68_000, 40, 0.66, 0),
    Product("PLT-T12", "Plataforma tesoura elétrica 12 m", "Plataformas elevatórias", "un", None, None, 5_300, 94_000, 30, 0.64, 0),
    Product("PLT-A16", "Plataforma articulada diesel 16 m", "Plataformas elevatórias", "un", None, None, 9_600, 245_000, 18, 0.62, 0),
    Product("PLT-A20", "Plataforma articulada diesel 20 m", "Plataformas elevatórias", "un", None, None, 12_800, 330_000, 10, 0.58, 0),
    # Compactação: locação e venda
    Product("CMP-PV90", "Placa vibratória 90 kg", "Compactação", "un", 14_500, 0.63, 1_150, 12_800, 24, 0.70, 0.9),
    Product("CMP-SAP", "Compactador de solo tipo sapo", "Compactação", "un", 19_800, 0.64, 1_450, 17_500, 26, 0.62, 0.7),
    Product("CMP-RL25", "Rolo compactador 2,5 t", "Compactação", "un", None, None, 7_400, 165_000, 10, 0.55, 0),
    # Andaimes: venda e locação (conjunto)
    Product("AND-TB", "Andaime tubular (conjunto 10 m²)", "Andaimes", "cj", 6_900, 0.58, 520, 5_600, 90, 0.60, 1.4),
    # Iluminação
    Product("ILU-TR4", "Torre de iluminação LED 4x300 W", "Iluminação", "un", 49_000, 0.65, 3_300, 44_000, 22, 0.58, 0.25),
    # Compressores: venda
    Product("CPR-250", "Compressor de ar 250 pcm", "Compressores", "un", 96_000, 0.68, None, None, 0, 0, 0.10),
    Product("CPR-400", "Compressor de ar 400 pcm", "Compressores", "un", 142_000, 0.69, None, None, 0, 0, 0.04),
    # Ferramentas: venda
    Product("FER-MRT", "Martelete rompedor 30 kg", "Ferramentas", "un", 7_400, 0.61, None, None, 0, 0, 3.0),
    Product("FER-CRT", "Cortadora de piso 14\"", "Ferramentas", "un", 9_900, 0.62, None, None, 0, 0, 2.2),
    Product("FER-VBR", "Vibrador de concreto 2 HP", "Ferramentas", "un", 3_600, 0.60, None, None, 0, 0, 3.4),
    # Peças e acessórios: venda
    Product("PCA-FLT", "Kit de filtros para gerador", "Peças e acessórios", "kit", 890, 0.55, None, None, 0, 0, 5.0),
    Product("PCA-BAT", "Bateria 12 V 150 Ah", "Peças e acessórios", "un", 1_450, 0.57, None, None, 0, 0, 4.0),
    Product("PCA-CAB", "Cabo de força 50 mm² (rolo 50 m)", "Peças e acessórios", "rl", 4_300, 0.59, None, None, 0, 0, 2.4),
    Product("PCA-DIS", "Disco diamantado 350 mm", "Peças e acessórios", "un", 690, 0.52, None, None, 0, 0, 6.0),
]

# Código legado que aparece no cadastro e em pedidos antigos para o mesmo produto.
LEGACY_PRODUCT_CODES = {
    "GER55-OLD": ("GER-055", "GERADOR 55KVA DIESEL (COD ANTIGO)"),
    "AND-TUB-10": ("AND-TB", "Andaime tubular 10m2 - conjunto"),
}

# Variações de descrição livres usadas nos itens de pedido
DESCRIPTION_VARIANTS = {
    "GER-055": ["GERADOR 55 KVA", "Gerador 55kva diesel", "Ger. diesel 55 kVA"],
    "GER-030": ["GERADOR 30KVA", "Gerador 30 kva"],
    "AND-TB": ["ANDAIME TUBULAR CJ", "Andaime tubular conj."],
    "PLT-T08": ["Tesoura 8m eletrica", "PLATAFORMA TESOURA 8M"],
    "CMP-SAP": ["Sapo compactador", "COMPACTADOR SAPO"],
    "FER-MRT": ["Martelete 30kg", "MARTELO ROMPEDOR 30 KG"],
}

STAGES_SALE = ["CREATED", "CREDIT_REVIEW", "APPROVED", "PICKING", "INVOICED", "DELIVERED"]
STAGES_RENTAL = ["CREATED", "CREDIT_REVIEW", "APPROVED", "PICKING", "DELIVERED"]

SUPPLIERS = {
    "inventory_purchase": ["Fornecedora Tarvon Máquinas", "Distribuidora Quelmar", "Importadora Brisel"],
    "fleet_capex": ["Fabricante Ondeval", "Máquinas Serrano Norte"],
    "maintenance": ["Oficina Lumer", "Assistência Técnica Varzeli"],
    "freight": ["Transportes Coriba", "Logística Pampelo"],
    "operating_expenses": ["Folha e encargos", "Aluguel e utilidades", "Serviços administrativos"],
}
