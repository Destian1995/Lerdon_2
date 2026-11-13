"""Build a deployment archive without configuration, keys or development files."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def package(destination=None):
    source=ROOT/'server/payments'
    destination=Path(destination or ROOT/'.release/lerdon-pay-server.zip')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.write(source/'README.md','ИНСТРУКЦИЯ.md')
        for name in ('Billing.php','Crypto.php','bootstrap.php','config.example.php','setup.php','cron.php','receipts.php','gifts.php','.htaccess'):
            archive.write(source/'private'/name,'lerdon-pay-private/'+name)
        archive.write(source/'schema.sql','lerdon-pay-private/schema.sql')
        for name in ('index.php','api.php','manage.php','.htaccess'):
            archive.write(source/'public'/name,'www/pay.katin-sharic.ru/'+name)
    return destination


if __name__=='__main__':
    print(package())
