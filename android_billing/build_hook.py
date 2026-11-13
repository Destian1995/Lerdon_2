"""p4a hook after manifest generation; SDK 8.6 requires AGP 8.9+ / Gradle 8.11.1."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def before_apk_assemble(toolchain):
    dist=Path(toolchain._dist.dist_dir)
    gradle=dist/'build.gradle'
    source=gradle.read_text(encoding='utf-8')
    source=re.sub(r'com.android.tools.build:gradle:[^\'\"]+',
                  'com.android.tools.build:gradle:8.9.2',source)
    if 'resValue "string", "ym_app_scheme"' not in source:
        source=source.replace('defaultConfig {','defaultConfig {\n        resValue "string", "ym_app_scheme", "lerdon-yookassa"',1)
    # AGP otherwise loads the entire multi-gigabyte p4a archive to compress it.
    # p4a reads the tar directly; storing it avoids excessive build-time memory.
    if 'noCompress "tar"' not in source:
        source=source.replace('android {','android {\n    androidResources { noCompress "tar" }',1)
    gradle.write_text(source,encoding='utf-8')
    wrapper=dist/'gradle/wrapper/gradle-wrapper.properties'
    source=wrapper.read_text(encoding='utf-8')
    source=re.sub(r'gradle-[\d.]+-(?:all|bin)\.zip','gradle-8.11.1-bin.zip',source)
    wrapper.write_text(source,encoding='utf-8')
    # p4a's extra_manifest_application_arguments inserts ATTRIBUTES, not child
    # nodes. Add the SDK bridge activity after p4a renders the valid manifest.
    manifest=dist/'src/main/AndroidManifest.xml'
    if not manifest.exists():raise RuntimeError('Generated AndroidManifest.xml missing')
    android='http://schemas.android.com/apk/res/android'
    ET.register_namespace('android',android)
    ET.register_namespace('tools','http://schemas.android.com/tools')
    tree=ET.parse(manifest);application=tree.getroot().find('application')
    if application is None:raise RuntimeError('Android application element missing')
    fragment=ET.fromstring('<application xmlns:android="'+android+'">'+
                          Path(__file__).with_name('application.xml').read_text(encoding='utf-8')+'</application>')
    for node in fragment:
        if not any(old.tag==node.tag and old.get('{'+android+'}name')==node.get('{'+android+'}name') for old in application):
            application.append(node)
    tree.write(manifest,encoding='utf-8',xml_declaration=True)
