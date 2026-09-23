"""Contrato de colunas esperado para cada arquivo de origem.

Mantido separado do gerador: é a expectativa da ingestão sobre a fonte.
Um teste garante que o gerador respeita o contrato.
"""

SOURCE_CONTRACTS: dict[str, list[str]] = {
    "customers": ["customer_id", "legal_name", "tax_id", "segment", "region", "city", "state",
                  "salesperson_id", "credit_limit", "created_at"],
    "products": ["sku", "description", "product_line", "unit_of_measure", "sale_list_price",
                 "rental_monthly_rate", "is_rentable", "is_sellable"],
    "equipment_units": ["unit_id", "sku", "serial_number", "acquisition_date", "acquisition_cost",
                        "branch", "retired_at"],
    "orders": ["order_id", "order_type", "customer_id", "salesperson_id", "order_date", "channel"],
    "order_items": ["order_item_id", "order_id", "sku", "product_description", "quantity",
                    "unit_list_price", "discount_amount", "unit_cost"],
    "order_events": ["event_id", "order_id", "stage_code", "event_at"],
    "rental_contracts": ["contract_id", "order_id", "customer_id", "start_date", "planned_end_date",
                         "actual_end_date", "billing_cycle"],
    "rental_contract_items": ["contract_item_id", "contract_id", "unit_id", "sku", "start_date",
                              "end_date", "list_monthly_rate", "agreed_monthly_rate"],
    "maintenance_orders": ["maintenance_id", "unit_id", "maintenance_type", "opened_at", "closed_at",
                           "description", "cost_amount"],
    "direct_costs": ["cost_id", "reference_type", "reference_id", "cost_type", "cost_date", "amount"],
    "receivables": ["receivable_id", "customer_id", "origin_type", "origin_id", "document_number",
                    "issue_date", "due_date", "amount"],
    "receipts": ["receipt_id", "receivable_id", "receipt_date", "amount", "method"],
    "payables": ["payable_id", "supplier_name", "category", "issue_date", "due_date", "amount"],
    "disbursements": ["disbursement_id", "payable_id", "paid_date", "amount"],
}
