import base64
from odoo import http
from odoo.http import request


class MngPrinterController(http.Controller):

    @http.route('/mng_printer/stream_pdf', type='http', auth='user', csrf=False)
    def stream_pdf(self, model='mng.print.queue', id=None, field='pdf_data', **kwargs):
        if not id:
            return request.not_found()
        try:
            record = request.env[model].browse(int(id))
            if not record.exists():
                return request.not_found()
            pdf_data = getattr(record, field, None)
            if not pdf_data:
                return request.not_found()

            if isinstance(pdf_data, str):
                pdf_bytes = base64.b64decode(pdf_data)
            elif isinstance(pdf_data, bytes):
                pdf_bytes = base64.b64decode(pdf_data) if not pdf_data.startswith(b"%PDF") else pdf_data
            else:
                return request.not_found()

            filename = getattr(record, 'pdf_filename', 'document.pdf') or 'document.pdf'
            return request.make_response(
                pdf_bytes,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'inline; filename="{filename}"'),
                ]
            )
        except Exception as e:
            return request.not_found()
