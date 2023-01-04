
{
    'name': 'Payment Counterpart',
    'version': '0.01',
    'author': 'Ing. Leonel Fuentes Marrero',
    'category': 'Extra',
    'summary': 'Payment Counterpart Invoice/Credit Note',
    'depends': [
	    "account_check_printing", "snailmail_account"
    ],
    'description': """
    Module that allows you to match invoices with credit notes and vice versa, 
    in addition to odoo natural payments in the same interface in a generic way.
    """,
    'data': [
        "views/account_payment_view.xml",
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}

