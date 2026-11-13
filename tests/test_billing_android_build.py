from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import xml.etree.ElementTree as ET
from android_billing.build_hook import before_apk_assemble


class BillingAndroidBuildTests(unittest.TestCase):
    def test_hook_upgrades_toolchain_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'gradle/wrapper').mkdir(parents=True)
            gradle=root/'build.gradle';wrapper=root/'gradle/wrapper/gradle-wrapper.properties'
            (root/'src/main').mkdir(parents=True)
            manifest=root/'src/main/AndroidManifest.xml'
            manifest.write_text('<manifest><application /></manifest>')
            gradle.write_text("classpath 'com.android.tools.build:gradle:8.1.1'\nandroid { defaultConfig { minSdkVersion 24 } }")
            wrapper.write_text('distributionUrl=https\\://services.gradle.org/distributions/gradle-8.0.2-all.zip')
            toolchain=SimpleNamespace(_dist=SimpleNamespace(dist_dir=folder))
            before_apk_assemble(toolchain);before_apk_assemble(toolchain)
            self.assertIn('gradle:8.9.2',gradle.read_text())
            self.assertEqual(gradle.read_text().count('resValue "string", "ym_app_scheme"'),1)
            self.assertEqual(gradle.read_text().count('noCompress "tar"'),1)
            self.assertIn('gradle-8.11.1-bin.zip',wrapper.read_text())
            application=ET.parse(manifest).getroot().find('application')
            self.assertEqual(len(application.findall('activity')),1)
            self.assertEqual(application.find('activity').get('{http://schemas.android.com/apk/res/android}exported'),'false')

    def test_sdk_activity_cannot_be_started_by_external_apps(self):
        xml=Path('android_billing/application.xml').read_text()
        tree=ET.fromstring('<application xmlns:android="http://schemas.android.com/apk/res/android">'+xml+'</application>')
        activity=tree.find('activity')
        self.assertEqual(activity.get('{http://schemas.android.com/apk/res/android}exported'),'false')


if __name__=='__main__':unittest.main()
