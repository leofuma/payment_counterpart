
{
    'name': 'Payment Counterpart',
    'version': '0.01',
    'author': 'Reserva',
    'category': 'Extra',
    'summary': 'Check',
    'depends': [
	    "account_check_printing",
    ],
    'description': """
    """,
    'data': [
        "security/ir.model.access.csv",
	    "data/report_paperformat.xml",
	    "report_check.xml",
        "views/account_payment_view.xml",
    ],
}

