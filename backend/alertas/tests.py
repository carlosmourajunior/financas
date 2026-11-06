from unittest import mock

from django.contrib.auth import authenticate, get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

from alertas import telegram

AMBIENTE = {'TELEGRAM_BOT_TOKEN': 't', 'TELEGRAM_CHAT_ID': '1', 'ALERTA_ORIGEM': 'teste'}


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class AlertasTests(TestCase):
    def setUp(self):
        cache.clear()
        self.rf = RequestFactory()

    def test_sem_token_nao_envia(self):
        with mock.patch.dict('os.environ', {}, clear=True), \
             mock.patch.object(telegram, '_enviar') as enviar:
            self.assertFalse(telegram.alertar('x'))
        enviar.assert_not_called()

    def test_deduplica_pela_chave(self):
        with mock.patch.dict('os.environ', AMBIENTE), \
             mock.patch.object(telegram.threading, 'Thread') as thread:
            self.assertTrue(telegram.alertar('x', chave='k'))
            self.assertFalse(telegram.alertar('x', chave='k'))
        self.assertEqual(thread.call_count, 1)

    def test_ip_prefere_cloudflare(self):
        req = self.rf.get('/', HTTP_CF_CONNECTING_IP='1.2.3.4', HTTP_X_FORWARDED_FOR='5.6.7.8')
        self.assertEqual(telegram.ip_cliente(req), '1.2.3.4')
        req = self.rf.get('/', HTTP_X_FORWARDED_FOR='5.6.7.8, 10.0.0.1')
        self.assertEqual(telegram.ip_cliente(req), '5.6.7.8')

    def test_alerta_apos_falhas_de_login(self):
        req = self.rf.post('/', HTTP_CF_CONNECTING_IP='9.9.9.9')
        with mock.patch('alertas.sinais.alertar') as alertar:
            for _ in range(5):
                authenticate(request=req, username='naoexiste', password='errada')
        alertar.assert_called_once()
        self.assertIn('9.9.9.9', alertar.call_args[0][0])

    def test_login_de_admin_alerta(self):
        User = get_user_model()
        campos = {User.USERNAME_FIELD: 'adm@example.com', 'password': 'Senha-forte-123'}
        if User.USERNAME_FIELD != 'username' and 'username' in [f.name for f in User._meta.fields]:
            campos['username'] = 'adm'
        User.objects.create_superuser(**campos)
        with mock.patch('alertas.sinais.alertar') as alertar:
            u = authenticate(request=self.rf.post('/'), **{User.USERNAME_FIELD: 'adm@example.com',
                                                           'password': 'Senha-forte-123'})
            self.assertIsNotNone(u)
            from django.contrib.auth.signals import user_logged_in
            user_logged_in.send(sender=User, request=self.rf.post('/'), user=u)
        alertar.assert_called_once()
