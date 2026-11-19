"""Conjunto de validação (holdout) da categorização, separado do conjunto de variações.

Escrito de uma vez, sem consultar as regras do categorizador e **sem ajuste das regras depois da
medição**: serve para estimar o acerto em textos que as regras não viram. Na primeira medição
(92/111 = 82,9%), 17 dos 19 erros eram de rótulo, e não do categorizador: o conjunto usava uma
categoria "compras" que o Trokim não tem. Um (IPTU) mudou a convenção: com a categoria
``impostos``, IPTU passou de ``moradia`` para ``impostos``, junto do IPVA. O erro que sobra
(Zaffari) é real e fica no conjunto. Os rótulos foram alinhados às convenções da taxonomia
(``docs/arquitetura/categorias.md``): varejo em ``servicos``, passagem aérea e pet shop em
``lazer``, internet residencial em ``moradia``. Só marcas públicas e nomes
genéricos inventados; nenhum dado real. Mesmo formato de ``categorizacao_variacoes``.
"""

D, C = "D", "C"

CASOS: list[tuple[str, str, str]] = [
    # alimentação
    ("IFD*PIZZARIA FORNO A LENHA", D, "alimentacao"),
    ("MERCADINHO SAO JORGE", D, "alimentacao"),
    ("HORTIFRUTI CENTRAL", D, "alimentacao"),
    ("ACOUGUE BOI GORDO", D, "alimentacao"),
    ("PADARIA PAO QUENTE", D, "alimentacao"),
    ("LANCHONETE DA ESQUINA", D, "alimentacao"),
    ("CHURRASCARIA GAUCHA", D, "alimentacao"),
    ("SUSHI KOI", D, "alimentacao"),
    ("BURGER KING 0412", D, "alimentacao"),
    ("MCDONALDS MC 123", D, "alimentacao"),
    ("SUBWAY SHOPPING", D, "alimentacao"),
    ("STARBUCKS PAULISTA", D, "alimentacao"),
    ("CAFETERIA GRÃO FINO", D, "alimentacao"),
    ("SORVETERIA GELATO", D, "alimentacao"),
    ("PAG*ACAI DO PORTO", D, "alimentacao"),
    ("ATACADAO 045", D, "alimentacao"),
    ("SAMS CLUB", D, "alimentacao"),
    ("ZAFFARI BOURBON", D, "alimentacao"),
    ("GUANABARA SUPERMERCADOS", D, "alimentacao"),
    ("HABIBS 0123", D, "alimentacao"),
    # transporte
    ("UBER *TRIP HELP.UBER.COM", D, "transporte"),
    ("99APP *99POP", D, "transporte"),
    ("POSTO IPIRANGA BR 101", D, "transporte"),
    ("AUTO POSTO SHELL", D, "transporte"),
    ("POSTO PETROBRAS CENTRO", D, "transporte"),
    ("SEM PARAR", D, "transporte"),
    ("CONECTCAR", D, "transporte"),
    ("ESTACIONAMENTO ESTAPAR", D, "transporte"),
    ("METRO SP BILHETE", D, "transporte"),
    ("RECARGA BILHETE UNICO", D, "transporte"),
    ("LATAM AIRLINES", D, "lazer"),
    ("GOL LINHAS AEREAS", D, "lazer"),
    ("AZUL LINHAS AEREAS", D, "lazer"),
    ("BUSER VIAGENS", D, "transporte"),
    ("OFICINA MECANICA DO ZE", D, "transporte"),
    ("PNEUS E RODAS LTDA", D, "transporte"),
    ("DETRAN LICENCIAMENTO", D, "impostos"),
    ("IPVA 2026 COTA UNICA", D, "impostos"),
    # moradia
    ("ALUGUEL APTO 101", D, "moradia"),
    ("CONDOMINIO RESIDENCIAL PARQUE", D, "moradia"),
    ("ENEL DISTRIBUICAO", D, "moradia"),
    ("CEMIG DISTRIBUICAO", D, "moradia"),
    ("SABESP CONTA AGUA", D, "moradia"),
    ("COMGAS", D, "moradia"),
    ("LIGHT SERVICOS ELETRICIDADE", D, "moradia"),
    ("LEROY MERLIN", D, "moradia"),
    ("TELHA NORTE", D, "moradia"),
    ("MATERIAL DE CONSTRUCAO SILVA", D, "moradia"),
    ("IPTU 2026 PARCELA 3", D, "impostos"),
    # saúde
    ("DROGARIA VENANCIO", D, "saude"),
    ("FARMACIA POPULAR", D, "saude"),
    ("PAGUE MENOS 0234", D, "saude"),
    ("UNIMED SEGUROS", D, "saude"),
    ("AMIL ASSISTENCIA MEDICA", D, "saude"),
    ("LABORATORIO FLEURY", D, "saude"),
    ("CLINICA ODONTOLOGICA SORRISO", D, "saude"),
    ("HOSPITAL SAO LUIZ", D, "saude"),
    ("SMARTFIT MENSALIDADE", D, "saude"),
    ("TOTALPASS PLANO", D, "saude"),
    # educação
    ("UDEMY ONLINE COURSES", D, "educacao"),
    ("ALURA CURSOS", D, "educacao"),
    ("MENSALIDADE FACULDADE", D, "educacao"),
    ("COLEGIO SANTA MARIA", D, "educacao"),
    ("LIVRARIA CULTURA", D, "educacao"),
    ("ESCOLA DE IDIOMAS WIZARD", D, "educacao"),
    ("COURSERA", D, "educacao"),
    # lazer
    ("NETFLIX.COM", D, "lazer"),
    ("SPOTIFY P1234", D, "lazer"),
    ("CINEMARK SHOPPING", D, "lazer"),
    ("INGRESSO.COM", D, "lazer"),
    ("STEAM PURCHASE", D, "lazer"),
    ("PLAYSTATION NETWORK", D, "lazer"),
    ("DISNEY PLUS", D, "lazer"),
    ("HBO MAX", D, "lazer"),
    ("BOOKING.COM HOTEL", D, "lazer"),
    ("AIRBNB * HMXYZ", D, "lazer"),
    ("BAR DO MANE", D, "lazer"),
    ("SYMPLA INGRESSOS", D, "lazer"),
    # compras
    ("AMAZON MARKETPLACE", D, "servicos"),
    ("MAGAZINE LUIZA", D, "servicos"),
    ("SHOPEE *LOJA", D, "servicos"),
    ("ALIEXPRESS", D, "servicos"),
    ("RENNER LOJA 120", D, "servicos"),
    ("RIACHUELO", D, "servicos"),
    ("CENTAURO", D, "servicos"),
    ("KABUM", D, "servicos"),
    ("CASAS BAHIA", D, "servicos"),
    ("SHEIN", D, "servicos"),
    ("ZARA BRASIL", D, "servicos"),
    ("PETZ PET SHOP", D, "lazer"),
    # serviços
    ("VIVO FIXO E INTERNET", D, "moradia"),
    ("CLARO TV E INTERNET", D, "moradia"),
    ("TIM PRE RECARGA", D, "servicos"),
    ("GOOGLE STORAGE", D, "servicos"),
    ("APPLE.COM/BILL", D, "servicos"),
    ("TARIFA PACOTE SERVICOS", D, "servicos"),
    ("LAVANDERIA 5ASEC", D, "servicos"),
    ("BARBEARIA DO CORTE", D, "servicos"),
    ("SALAO DE BELEZA BELLA", D, "servicos"),
    # impostos
    ("DARF RECEITA FEDERAL", D, "impostos"),
    ("DAS SIMPLES NACIONAL", D, "impostos"),
    ("GPS INSS CONTRIBUINTE", D, "impostos"),
    # renda
    ("SALARIO EMPRESA EXEMPLO", C, "renda"),
    ("PROVENTOS FOLHA", C, "renda"),
    ("RENDIMENTO POUPANCA", C, "renda"),
    ("PIX RECEBIDO CLIENTE", C, "renda"),
    ("TED RECEBIDA EMPRESA", C, "renda"),
    # sem como inferir
    ("PIX ENVIADO MARIA EXEMPLO", D, "outros"),
    ("TRANSFERENCIA ENVIADA", D, "outros"),
    ("PAGAMENTO DIVERSOS", D, "outros"),
    ("SAQUE 24H", D, "outros"),
]
