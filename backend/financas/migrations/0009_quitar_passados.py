from datetime import date

from django.db import migrations


def quitar(apps, schema_editor):
    # Tudo que tem data antes de hoje passa a contar como pago ou recebido.
    apps.get_model("financas", "Lancamento").objects.filter(pago=False, data__lt=date.today()).update(pago=True)


class Migration(migrations.Migration):
    dependencies = [("financas", "0008_categoria_cor")]

    operations = [migrations.RunPython(quitar, migrations.RunPython.noop)]
