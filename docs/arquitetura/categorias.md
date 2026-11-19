# Categorias dos gastos

A categoria de cada lançamento é decidida **por código, sem LLM**, na hora da importação
(`api/app/services/categorization_service.py`). O usuário pode corrigir no app, e a correção vira
regra do estabelecimento ([ADR 0018](../adr/0018-contas-periodos-transferencias-e-visoes.md)).

## Taxonomia e convenções

| Categoria | Chave na API | Entra aqui | Convenção |
|---|---|---|---|
| Alimentação | `alimentacao` | mercados, padarias, restaurantes, delivery | |
| Moradia | `moradia` | aluguel, condomínio, energia, água, gás, internet residencial, material de construção, móveis | internet e TV por assinatura da casa ficam aqui |
| Transporte | `transporte` | combustível, aplicativos de corrida, pedágio, estacionamento, ônibus e metrô, oficina, aluguel de carro | |
| Saúde | `saude` | farmácias, planos, clínicas, laboratórios, ótica, **academias** (Smart Fit, TotalPass, Wellhub/Gympass) | academia é saúde, não lazer |
| Educação | `educacao` | escolas, faculdades, cursos, livrarias, papelarias | |
| Lazer e bem-estar | `lazer` | streaming, cinema, shows, jogos, bares, **viagem** (passagem aérea, hotel), **pet** | passagem aérea e pet shop ficam em lazer |
| Serviços | `servicos` | telefonia, assinaturas digitais, tarifas bancárias, beleza, lavanderia e **varejo em geral** (Amazon, Mercado Livre, lojas de roupa e eletrônicos) | não há categoria "compras": varejo fica em serviços |
| Impostos e taxas | `impostos` | DARF, DAS do Simples, GPS/INSS, IPVA, **IPTU**, Detran, prefeitura | só para saídas; entrada da prefeitura ou do INSS é renda |
| Renda | `renda` | salário, Pix e TED recebidos, rendimentos | só para entradas |
| Outros | `outros` | o que não dá para inferir: Pix para pessoas, saque, textos vagos | |

Pagamento de fatura, transferências entre contas próprias e investimentos não têm categoria: não
são gasto nem renda ([ADR 0017](../adr/0017-perfis-de-banco-e-natureza-do-lancamento.md)).

## Ordem de decisão

1. **Regra do usuário** para o estabelecimento, quando existir (vale sobre todas as outras).
2. **Regras por palavra inteira**, sem acento e sem diferenciar caixa. Cobrem marcas e termos no
   formato de vários bancos e adquirentes (`IFD*`, `MP*`, `PAG*`, `EC*`, `SUMUP*`...), inclusive
   nomes colados (`SUPERMERCADOBOMPRECO`).
3. **Dicionário de redes**: nomes fantasia de empresas com 20 ou mais estabelecimentos ativos,
   com a categoria da atividade econômica ([ADR 0020](../adr/0020-categorizacao-por-cnae.md)).
4. **Atividade da empresa (CNAE)** pelo CNPJ do recebedor, quando o banco o informa (Pix do
   Nubank) e o índice local existe. Só para saídas, e nunca por CPF.
5. **Categoria do próprio banco**, quando o arquivo traz e nada acima decidiu (fatura Ourocard do
   BB em PDF).
6. Entrada sem regra vira **Renda**; o resto fica em **Outros**.

## Como a categorização é medida

| Conjunto | Casos | O que mede | Teste |
|---|---:|---|---|
| Variações de formato | 259 | Regressão: acompanhou o ajuste das regras, então o acerto aqui é otimista | `api/tests/data/categorizacao_variacoes.py` (mínimo de 95%) |
| Validação (holdout) | 111 | Acerto em textos novos: escrito sem olhar as regras e sem ajuste depois | `api/tests/data/categorizacao_holdout.py` (meta de 80%) |

Na primeira medição, o holdout deu **82,9%**. Dos 19 erros, 17 eram de rótulo (o conjunto usava
uma categoria "compras" que o Trokim não tem) e um mudou a convenção do IPTU, que passou de moradia
para impostos. Corrigidos os rótulos, ficou em **99,1%** (110/111). O erro que sobra (Zaffari)
fica no conjunto. Com o dicionário de redes, o conjunto de variações está em 98,8% (256/259). Os dois conjuntos usam só marcas públicas e nomes inventados.

### Extratos reais do desenvolvedor

Medição feita só na máquina do desenvolvedor, sem copiar arquivos para o repositório e sem
imprimir nomes ou documentos. O resultado depende do perfil de cada pessoa: quem paga mais por Pix
a pessoas físicas fica com mais gastos em Outros, porque esses gastos não têm como ser inferidos.

| Etapa | Gastos com categoria | Sem contar Pix para pessoas | Valor com categoria |
|---|---:|---:|---:|
| Antes desta entrega | 49% | — | — |
| Regras por formato de vários bancos | 56% | 75% | 28% |
| Mais o dicionário de redes (sem o índice) | 56% | 75% | 28% |
| Mais a atividade (CNAE) pelo CNPJ do recebedor | **67%** | **89%** | **62%** |

São 105 gastos de outubro e junho de 2026 em quatro arquivos (Nubank conta e cartão, BB conta e
fatura). O ganho veio todo do CNAE, nos Pix do Nubank para empresas: a conta do Nubank foi de 45%
para 63% dos gastos e de 28% para 77% do valor. No extrato da conta do BB, que não traz o CNPJ nem
o nome do recebedor de forma útil, nada mudou (0 de 11). Nos extratos do desenvolvedor, o
dicionário de redes não pegou nenhum gasto que as regras já não pegassem; ele serve para quem
compra em redes regionais que as regras por palavra não conhecem. Dos gastos que ficaram em Outros,
26 de 35 são Pix para pessoas.
