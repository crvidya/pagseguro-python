# -*- coding: utf-8 -*-
from pagseguro.api.base_payment import BasePaymentRequest
from pagseguro.api.v2 import settings
from pagseguro.api.v2.schemas import item_schema, client_schema, shipping_schema
from pagseguro.exceptions import PagSeguroApiException, \
    PagSeguroPaymentException
from xml.etree import ElementTree
import dateutil.parser
import logging
import requests

logger = logging.getLogger(__name__)


class Payment(BasePaymentRequest):
    ''' Classe que implementa a requisição à API do PagSeguro versão 2
    
    .. todo::
        Incluir metadata
    
    Args:
        email (str): (obrigatório) O email da sua conta no PagSeguro
        token (str): (obrigatório) O seu token de acesso ao PagSeguro

    '''

    def __init__(self,
                 email,
                 token,
                 receiver_email=None,
                 currency='BRL',
                 reference=None,
                 extra_amount=None,
                 redirect_url=None,
                 notification_url=None,
                 max_uses=None,
                 max_age=None):

        self.email = email
        self.token = token
        self.receiver_email = receiver_email
        self.currency = currency
        self.reference = reference

        self.extra_amount = extra_amount
        self.redirect_url = redirect_url
        self.notification_url = notification_url
        self.max_uses = max_uses
        self.max_age = max_age
        self.items = []
        self.client = {}
        self.shipping = {}
        self.response = None

    def api_version(self):
        return u'2.0'

    def add_item(self, item_id, description, amount, quantity, shipping_cost=None, weight=None):
        item = {}
        item['item_id'] = item_id
        item['description'] = description
        item['amount'] = float(amount)
        item['quantity'] = quantity
        if shipping_cost:
            item['shipping_cost'] = shipping_cost
        if weight:
            item['weight'] = weight
        # Validar dados
        item_schema(item)
        self.items.append(item)

    def set_client(self, *args, **kwargs):
        ''' Inclui dados do comprador

        Args:
            name (str): (opcional) Nome do cliente
            email (str): (opcional) Email do cliente
            phone_area_code (str): (opcional) Código de área do telefone do cliente. Um número com 2 digitos.
            phone_number (str): (opcional) O número de telefone do cliente.
            cpf: (str): (opcional) Número do cpf do comprador
            born_date: (date): Data de nascimento no formato dd/MM/yyyy
        '''
        self.client = {}      
        for arg, value in kwargs.iteritems():
            self.client[arg] = value
        client_schema(self.client)

    def set_shipping(self, *args, **kwargs):
        ''' Define os atributos do frete

        Args:
            type (int): (opcional) Tipo de frete. Os valores válidos são: 1 para 'Encomenda normal (PAC).',
                2 para 'SEDEX' e 3 para 'Tipo de frete não especificado.'
            cost (float): (opcional) Valor total do frete. Deve ser maior que 0.00 e menor ou igual a 9999999.00.
            street (str): (opcional) Nome da rua do endereço de envio do produto
            address_number: (opcional) Número do endereço de envio do produto. 
            complement: (opcional) Complemento (bloco, apartamento, etc.) do endereço de envio do produto. 
            district: (opcional) Bairro do endereço de envio do produto.
            postal_code: (opcional) CEP do endereço de envio do produto.
            city: (opcional) Cidade do endereço de envio do produto.
            state: (opcional) Estado do endereço de envio do produto.
            country: (opcional) País do endereço de envio do produto. Apenas o valor 'BRA' é aceito.
        
        '''
        self.shipping = {}
        for arg, value in kwargs.iteritems():
            self.shipping[arg] = value
        shipping_schema(self.shipping)

    def request(self):
        '''
        Faz a requisição de pagamento ao servidor do PagSeguro.
        '''
        params = self._build_params()
        req = requests.post(
            settings.PAGSEGURO_API_URL,
            params=params,
            headers={
                'Content-Type':
                'application/x-www-form-urlencoded; charset=ISO-8859-1'
            }
        )
        if req.status_code == 200:
            self.response = self._process_response_xml(req.text)
        else:
            raise PagSeguroApiException(
                u'Erro ao fazer request para a API:' +
                ' HTTP Status=%s - Response: %s' % (req.status_code, req.text))
        return

    def _build_params(self):
        ''' método que constrói o dicionario com os parametros que serão usados
        na requisição HTTP Post ao PagSeguro
        
        Returns:
            Um dicionário com os parametros definidos no objeto Payment.
        '''
        params = {}
        params['email'] = self.email
        params['token'] = self.token
        params['currency'] = self.currency

        # Atributos opcionais
        if self.receiver_email:
            params['receiver_email'] = self.receiver_email
        if self.reference:
            params['reference'] = self.reference
        if self.extra_amount:
            params['extra_amount'] = self.extra_amount
        if self.redirect_url:
            params['redirect_url'] = self.redirect_url
        if self.notification_url:
            params['notification_url'] = self.notification_url
        if self.max_uses:
            params['max_uses'] = self.max_uses
        if self.max_age:
            params['max_age'] = self.max_age

        #TODO: Incluir metadata aqui

        # Itens
        for index, item in enumerate(self.items, start=1):
            params['itemId%d' % index] = item['item_id']
            params['itemDescription%d' % index] = item['description']
            params['itemAmount%d' % index] = '%.2f' % item['amount']
            params['itemQuantity%s' % index] = item['quantity']
            if item.get('shipping_cost'):
                params['itemShippingCost%d' % index] = item['shipping_cost']
            if item.get('weight'):
                params['itemWeight%d' % index] = item['weight']

        # Sender
        if self.client.get('email'):
            params['senderEmail'] = self.client.get('email')
        if self.client.get('name'):
            params['senderName'] = self.client.get('name')
        if self.client.get('phone_area_code'):
            params['senderAreaCode'] = self.client.get('phone_area_code')
        if self.client.get('phone_number'):
            params['senderPhone'] = self.client.get('phone_number')
        if self.client.get('cpf'):
            params['senderCPF'] = self.client.get('cpf')
        if self.client.get('sender_born_date'):
            params['senderBornDate'] = self.client.get('sender_born_date')

        # Shipping
        if self.shipping.get('type'):
            params['shippingType'] = self.shipping.get('type')
        if self.shipping.get('cost'):
            params['shippingCost'] = '%.2f' % self.shipping.get('cost')
        if self.shipping.get('country'):
            params['shippingAddressCountry'] = self.shipping.get('country')
        if self.shipping.get('state'):
            params['shippingAddressState'] = self.shipping.get('state')
        if self.shipping.get('city'):
            params['shippingAddressCity'] = self.shipping.get('city')
        if self.shipping.get('postal_code'):
            params['shippingAddressPostalCode'] = self.shipping.get('postal_code')
        if self.shipping.get('district'):
            params['shippingAddressDistrict'] = self.shipping.get('district')
        if self.shipping.get('street'):
            params['shippingAddressStreet'] = self.shipping.get('street')
        if self.shipping.get('number'):
            params['shippingAddressNumber'] = self.shipping.get('number')
        if self.shipping.get('complement'):
            params['shippingAddressComplement'] = self.shipping.get('complement')

        return params

    def _process_response_xml(self, response_xml):
        '''
        Processa o xml de resposta e caso não existam erros retorna um
        dicionario com o codigo e data.

        :return: dictionary
        '''
        result = {}
        xml = ElementTree.fromstring(response_xml)
        if xml.tag == 'errors':
            logger.error(
                u'Erro no pedido de pagamento ao PagSeguro.' +
                ' O xml de resposta foi: %s' % response_xml)
            errors_message = u'Ocorreu algum problema com os dados do pagamento: '
            for error in xml.findall('error'):
                error_code = error.find('code').text
                error_message = error.find('message').text
                errors_message += u'\n (code=%s) %s' % (error_code,
                                                        error_message)
            raise PagSeguroPaymentException(errors_message)

        if xml.tag == 'checkout':
            result['code'] = xml.find('code').text

            try:
                xml_date = xml.find('date').text
                result['date'] = dateutil.parser.parse(xml_date)
            except:
                logger.exception(u'O campo date não foi encontrado ou é invalido')
                result['date'] = None
        else:
            raise PagSeguroPaymentException(
                u'Erro ao processar resposta do pagamento: tag "checkout" nao encontrada no xml de resposta')
        return result

    def payment_url(self):
        '''
        Retorna a url para onde o cliente deve ser redirecionado para
        continuar o fluxo de pagamento.

        :return: str, URL de pagamento
        '''
        if self.response:
            return u'%s?code=%s' % (settings.PAGSEGURO_API_URL, self.response['code'])
        else:
            return None
