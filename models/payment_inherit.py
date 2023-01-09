# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class AccountPayment(models.Model):
    _inherit = "account.payment"

    line_ids = fields.One2many('account.payment.line', 'payment_id', string='Payment Line', domain=[('funding', '=', False)])
    line_funding_ids = fields.One2many('account.payment.line', 'payment_id', string='Payment Line', domain=[('funding', '=', True)])
    payment_diff = fields.Monetary(compute='_compute_payment_diff', readonly=True)
    payment_diff_handling = fields.Selection([('open', 'Keep open'), ('reconcile', 'Reconcile Payment Balance')], default='open', string="Payment Difference", copy=False)
    partner_type = fields.Selection([('customer', 'Customer'), ('supplier', 'Vendor'), ('customer_supplier', 'Customer - Vendor')])
    partner_id = fields.Many2one('res.partner', string='Partner')
    automatic = fields.Boolean(string='Automatic', default=True)

    @api.one
    @api.depends('line_ids', 'amount', 'payment_date', 'currency_id', 'line_funding_ids', 'state', 'automatic')
    def _compute_payment_diff(self):
        t_funding = sum(line.amount for line in self.line_funding_ids)
        t_invoic = sum(line.amount for line in self.line_ids)
        payment_diff = t_invoic - (self.amount + t_funding)
        self.payment_diff = -payment_diff if self.payment_type == 'outbound' else payment_diff

    @api.multi
    def best_counterpart(self, amount):
        if amount > 0:
            for inv in self.line_ids:
                if (inv.residual - inv.amount) != 0:
                    if (inv.residual - inv.amount) <= amount:
                        minus = (inv.residual - inv.amount)
                        inv.amount = (inv.residual - inv.amount)
                        amount -= minus
        return amount

    @api.onchange('partner_type')
    def _onchange_partner_type(self):
        self.ensure_one()
        # Set partner_id domain
        if self.partner_type:
            if self.partner_type == 'customer_supplier':
                return {'domain': {'partner_id': [('customer', '=', True), ('supplier', '=', True)]}}
            else:
                return {'domain': {'partner_id': [(self.partner_type, '=', True)]}}

    @api.onchange('amount', 'line_funding_ids', 'line_ids', 'automatic')
    def onchange_amount(self):
        amountt, amount_invoice, amount_funding, amount = [0.0, 0.0, 0.0, 0.0]
        if self.automatic == True:
            for l in self.line_funding_ids:
                l.amount = 0
            amount_funding = sum(x.amount for x in self.line_funding_ids)
            amount_invoice = sum(x.amount for x in self.line_ids)
            # select a new offset element so I have to reapply the fund to the invoices to be paid
            if amount_funding != amount_invoice and amount_invoice != 0 and self.amount == 0:
                for invo in self.line_ids:
                    invo.amount = 0
                    invo.reconcile = False
            #change the amount to be paid from a non-zero number to another.
            if self.amount != amount_invoice and amount_invoice != 0 and amount_funding == 0:
                for invo in self.line_ids:
                    invo.amount = 0
                    invo.reconcile = False
            # Distribution of the amount of creditable invoices
            if self.line_funding_ids and sum(x.residual for x in self.line_funding_ids if x.reconcile) > 0:
                for lin in self.line_funding_ids:
                    amount_invoice = sum(x.amount for x in self.line_ids)
                    if lin.reconcile == True and lin.amount == 0:
                        if self.line_ids and lin.residual > 0 and (
                                (amount_invoice != lin.amount) or (lin.amount == 0 and amount_invoice == 0)):
                            amountt = self.amount
                            amount_funding = lin.residual
                            for line in self.line_ids:
                                if amount_funding > 0 and (line.residual - line.amount) != 0:
                                    if (line.residual - line.amount) <= amount_funding:
                                        minus = line.residual - line.amount
                                        line.amount += line.residual - line.amount
                                        amount_funding -= minus
                                        lin.amount += minus
                                    elif (line.residual - line.amount) > amount_funding:
                                        temp = amount_funding
                                        if line.amount > 0:
                                            amount_funding += line.amount
                                            line.amount = 0
                                        amount_funding = self.best_counterpart(amount_funding)
                                        lin.amount += temp - amount_funding
                                        line.amount += amount_funding
                                        lin.amount += amount_funding
                                        amount_funding = 0
            # Distribution of the amount entered by the user
            if self.line_ids and ((amount_invoice != self.amount) or (self.amount == 0 and amount_invoice == 0)):
                amountt = self.amount
                for line in self.line_ids:
                    if amountt > 0 and (line.residual - line.amount) != 0:
                        if (line.residual - line.amount) <= amountt:
                            minus = line.residual - line.amount
                            line.amount += line.residual - line.amount
                            amountt -= minus
                        elif (line.residual - line.amount) > amountt:
                            if line.amount > 0:
                                amountt += line.amount
                                line.amount = 0
                            amountt = self.best_counterpart(amountt)
                            line.amount += amountt
                            amountt = 0

            for l in self.line_ids:
                if l.amount == l.residual:
                    l.reconcile = True

            if sum(x.amount for x in self.line_funding_ids) == 0 and self.amount == 0:
                for invo in self.line_ids:
                    invo.amount = 0
                    invo.reconcile = False
            # # semi-Automatic version
            # amount_funding = sum(x.amount for x in self.line_funding_ids)
            # if amount_funding > 0 or self.amount > 0:
            #     self.automatic = False
        else:
            for l in self.line_funding_ids:
                if l.reconcile == True:
                    l.amount = l.residual
                if l.amount > l.residual:
                    l.amount = l.residual

            for l in self.line_ids:
                if l.reconcile == True:
                    l.amount = l.residual
                if l.amount > l.residual:
                    l.amount = l.residual



    @api.onchange('partner_id', 'payment_type', 'partner_type')
    def _get_payment_line(self):
        if self.env.context.get('active_model') and self.env.context['active_model'] == 'account.invoice':
            return
        type = []

        if self.payment_type == 'inbound' and self.partner_type == 'customer_supplier':
            type = ['out_invoice', 'in_refund']
        elif self.payment_type == 'outbound' and self.partner_type == 'customer_supplier':
            type = ['in_invoice', 'out_refund']
        elif self.payment_type == 'inbound' and self.partner_type == 'customer':
            type = ['out_invoice']
        elif self.payment_type == 'outbound' and self.partner_type == 'customer':
            type = ['out_refund']
        elif self.payment_type == 'inbound' and self.partner_type == 'supplier':
            type = ['in_refund']
        elif self.payment_type == 'outbound' and self.partner_type == 'supplier':
            type = ['in_invoice']

        liabilities = self.env['account.invoice'].search(
            [('partner_id', '=', self.partner_id.id), ('state', '=', 'open'), ('type', '=', type)], order='date_invoice asc')

        if self.payment_type == 'inbound' and self.partner_type == 'customer_supplier':
            type = ['in_invoice', 'out_refund']
        elif self.payment_type == 'outbound' and self.partner_type == 'customer_supplier':
            type = ['out_invoice', 'in_refund']
        elif self.payment_type == 'inbound' and self.partner_type == 'customer':
            type = ['out_refund']
        elif self.payment_type == 'outbound' and self.partner_type == 'customer':
            type = ['out_invoice']
        elif self.payment_type == 'inbound' and self.partner_type == 'supplier':
            type = ['in_invoice']
        elif self.payment_type == 'outbound' and self.partner_type == 'supplier':
            type = ['in_refund']

        funding = self.env['account.invoice'].search(
            [('partner_id', '=', self.partner_id.id), ('state', '=', 'open'), ('type', '=', type)])

        lines, lines_funding = [[], []]
        communication = ''
        for invoice in liabilities:
            vals = {'name': invoice.name_get()[0][1],
                    'invoice_id': invoice.id,
                    'funding': False}

            communication += "%s " % (invoice['reference'] or invoice['name'] or invoice['number'])
            lines.append((0, 0, vals))

        for invoice in funding:
            vals = {'name': invoice.name_get()[0][1],
                    'invoice_id': invoice.id,
                    'funding': True}

            communication += "%s " % (invoice['reference'] or invoice['name'] or invoice['number'])
            lines_funding.append((0, 0, vals))

        invoices = liabilities + funding

        self.line_ids = [(5, False, False)]
        self.line_ids = lines

        self.line_funding_ids = [(5, False, False)]
        self.line_funding_ids = lines_funding

        self.invoice_ids = [(6, 0, invoices.ids)]

        self.onchange_amount()

    @api.multi
    def do_print_checks(self):
        return self.env.ref('reserva_check_writer.action_report_check').report_action(self)

    def _create_payment_entry(self, amount):
        if not self.line_ids:
            payment_amount = self.amount
            for invoice in self.invoice_ids:
                vals = {'payment_id': self.id,
                        'invoice_id': invoice.id,
                        'residual': invoice.residual,
                        }
                if invoice.residual <= payment_amount:
                    vals['reconcile'] = True
                    vals['amount'] = invoice.residual
                    payment_amount -= invoice.residual
                elif invoice.residual > payment_amount:
                    vals['reconcile'] = False
                    vals['amount'] = payment_amount
                    payment_amount = 0
                self.env['account.payment.line'].create(vals)
            res = super(AccountPayment, self)._create_payment_entry(amount)
            return res
        else:
            """ Create a journal entry corresponding to a payment, if the payment references invoice(s) they are reconciled.
                Return the journal entry.
            """
            aml_obj = self.env['account.move.line'].with_context(check_move_validity=False)
            debit, credit, amount_currency, currency_id = aml_obj.with_context(date=self.payment_date)._compute_amount_fields(amount, self.currency_id, self.company_id.currency_id)

            move = self.env['account.move'].create(self._get_move_vals())

            # Write line corresponding to invoice payment
            for line in self.line_ids:
                if line.amount:
                    l_amount = line.amount * (line.payment_id.payment_type in ('outbound', 'transfer') and 1 or -1)
                    l_debit, l_credit, l_amount_currency, l_currency_id = aml_obj.with_context(date=self.payment_date)._compute_amount_fields(l_amount, self.currency_id, self.company_id.currency_id)
                    counterpart_aml_dict = self._get_shared_move_line_vals(l_debit, l_credit, l_amount_currency, move.id, False)
                    counterpart_aml_dict.update(self._get_counterpart_move_line_vals([line.invoice_id]))
                    counterpart_aml_dict.update({'currency_id': currency_id,'account_id': line.account_id.id})
                    counterpart_aml = aml_obj.create(counterpart_aml_dict)
                    line.invoice_id.register_payment(counterpart_aml)
                    line.residual_temp = line.residual + line.amount

            # Write line corresponding to invoice funding
            for line in self.line_funding_ids:
                if line.amount:
                    l_amount = line.amount * (line.payment_id.payment_type in ('outbound', 'transfer') and 1 or -1)
                    l_debit, l_credit, l_amount_currency, l_currency_id = aml_obj.with_context(date=self.payment_date)._compute_amount_fields(l_amount, self.currency_id, self.company_id.currency_id)
                    counterpart_aml_dict = self._get_shared_move_line_vals(l_credit, l_debit, -l_amount_currency, move.id, False)
                    counterpart_aml_dict.update(self._get_counterpart_move_line_vals([line.invoice_id]))
                    counterpart_aml_dict.update({'currency_id': currency_id,'account_id': line.account_id.id})
                    counterpart_aml = aml_obj.create(counterpart_aml_dict)
                    line.invoice_id.register_payment(counterpart_aml)
                    line.residual_temp = line.residual + line.amount

            if amount != 0:
                # Write counterpart lines
                if not self.currency_id != self.company_id.currency_id:
                    amount_currency = 0
                liquidity_aml_dict = self._get_shared_move_line_vals(credit, debit, -amount_currency, move.id, False)
                liquidity_aml_dict.update(self._get_liquidity_move_line_vals(-amount))
                aml_obj.create(liquidity_aml_dict)

                if self.payment_diff:
                    writeoff_line = self._get_shared_move_line_vals(0, 0, 0, move.id, False)
                    debit_wo, credit_wo, amount_currency_wo, currency_id = aml_obj.with_context(date=self.payment_date)._compute_amount_fields(self.payment_diff, self.currency_id, self.company_id.currency_id)
                    writeoff_line['name'] = _('Counterpart')
                    account_id = self.payment_type in ('outbound', 'transfer') and self.partner_id.property_account_payable_id.id or self.partner_id.property_account_receivable_id.id
                    if self.payment_diff_handling == 'reconcile':
                        account_id = self.writeoff_account_id.id
                    writeoff_line['account_id'] = account_id
                    writeoff_line['debit'] = debit_wo
                    writeoff_line['credit'] = credit_wo
                    writeoff_line['payment_id'] = self.id
                    writeoff_line['amount_currency'] = amount_currency_wo
                    writeoff_line['currency_id'] = currency_id
                    aml_obj.create(writeoff_line)

            # validate the payment
            if not self.journal_id.post_at_bank_rec:
                move.post()

            self.invoice_ids = [(4, line.invoice_id.id, None) for line in self.line_ids if line.amount]
            return move

    @api.multi
    def post(self):
        if self.env.context.get('active_model') and self.env.context['active_model'] == 'account.invoice':
            return super(AccountPayment, self).post()
        for res in self:
            res.invoice_ids = [(5, False, False)]
            res.invoice_ids = [(4, line.invoice_id.id, None) for line in res.line_ids if line.amount]

        for rec in self:
            if not rec.name:
                # Use the right sequence to set the name
                if rec.payment_type == 'transfer':
                    sequence_code = 'account.payment.transfer'
                else:
                    if rec.partner_type == 'customer':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.customer.invoice'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.customer.refund'
                    if rec.partner_type == 'supplier':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.supplier.refund'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.supplier.invoice'
                    if rec.partner_type == 'customer_supplier':
                        if rec.payment_type == 'inbound':
                            sequence_code = 'account.payment.customer_supplier.refund'
                        if rec.payment_type == 'outbound':
                            sequence_code = 'account.payment.customer_supplier.invoice'
                rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=rec.payment_date).next_by_code(sequence_code)
                if not rec.name and rec.payment_type != 'transfer':
                    raise UserError(_("You have to define a sequence for %s in your company.") % (sequence_code,))

        rec = super(AccountPayment, self.with_context(no_check_balance=True)).post()
        return rec


class AccountRegisterPayments(models.TransientModel):
    _inherit = "account.register.payments"

    @api.model
    def default_get(self, fields):
        rec = super(AccountRegisterPayments, self).default_get(fields)
        context = dict(self._context or {})
        active_model = context.get('active_model')
        active_ids = context.get('active_ids')
        invoices = self.env[active_model].browse(active_ids)
        communication = ' '
        for invoice in invoices:
            communication += "%s " % (invoice['reference'] or invoice['name'] or invoice['number'])

        rec.update({
            'communication': communication,
        })
        return rec


class AccountPaymentLine(models.Model):
    _name = "account.payment.line"
    _description = 'Account Payment Line'
    _rec_name = 'invoice_id'

    payment_id = fields.Many2one('account.payment', 'Payment')
    invoice_id = fields.Many2one('account.invoice', 'Invoice')
    account_id = fields.Many2one('account.account', 'Account', related="invoice_id.account_id")
    currency_id = fields.Many2one('res.currency', related="invoice_id.currency_id")
    amount_total = fields.Monetary('Original Amount', related="invoice_id.amount_total")
    residual = fields.Monetary('Open Balance', related='invoice_id.residual')
    amount = fields.Monetary('Allocation', currency_field='currency_id')
    reconcile = fields.Boolean('Full Reconcile', readonly=False)

    funding = fields.Boolean('Funding ?', compute='_compute_funding', store=True)
    amount_posted = fields.Monetary('Allocation', currency_field='currency_id', compute='_compute_amount_posted')
    type = fields.Selection('Type', related="invoice_id.type")
    residual_temp = fields.Monetary('Residual Temp')
    payment_type = fields.Selection('Payment Type', related='payment_id.payment_type')
    pay_automatic = fields.Boolean('Pay Automatic', related='payment_id.automatic')

    @api.one
    @api.depends('payment_type', 'type')
    def _compute_funding(self):

        if self.payment_type == 'inbound':
            if self.type in ['out_invoice', 'in_refund']:
                self.funding = False
            else:
                self.funding = True
        elif self.payment_type == 'outbound':
            if self.type in ['in_invoice', 'out_refund']:
                self.funding = False
            else:
                self.funding = True

    @api.one
    @api.depends('amount')
    def _compute_amount_posted(self):
        if self.residual == self.residual_temp:
            self.amount_posted = 0
            self.reconcile = False
        else:
            self.amount_posted = self.amount



