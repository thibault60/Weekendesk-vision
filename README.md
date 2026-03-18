# 🏖️ Weekendesk SEO Dashboard

Dashboard Streamlit pour le monitoring des performances SEO et Business de Weekendesk.

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
streamlit run weekendesk_dashboard.py
```

## Fonctionnalités

- 📈 **Clics SEO** : données statiques 2024-2026, comparaison YoY, heatmap
- 💼 **Performance Business** : import CSV Tableau, graphiques double-axe vs clics SEO
- 🔗 **Corrélations** : scatter plots, coefficients r/R², matrice de corrélation

## Format CSV attendu

| Dimension 1 | Date   | Measure Names | Measure Values |
|-------------|--------|---------------|----------------|
| seo         | Mar-26 | Purchases     | 12500          |
| seo         | Mar-26 | AOV           | 245.50         |
