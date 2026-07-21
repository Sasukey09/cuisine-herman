import 'package:file_selector/file_selector.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:foodgad_mobile/features/invoices/invoices_screen.dart';

/// Regression for the "Choisir un fichier" invoice button doing NOTHING on
/// iPhone/iPad.
///
/// Root cause: file_selector_ios (0.5.x) rejects any accepted-type group that
/// is not "allow all" yet carries no `uniformTypeIdentifiers`, by throwing an
/// `ArgumentError`. The invoice group used only `extensions` + `mimeTypes`, so
/// `openFile()` threw synchronously on iOS — and because it was called outside
/// a try/catch, the exception vanished and the button looked completely dead.
///
/// `_allowedUtiListIos` below is a faithful copy of file_selector_ios's
/// `_allowedUtiListFromTypeGroups`, so this test fails the moment the invoice
/// type group would again break the iOS picker.
List<String> _allowedUtiListIos(List<XTypeGroup>? typeGroups) {
  const allowAny = <String>['public.data'];
  if (typeGroups == null || typeGroups.isEmpty) return allowAny;
  final allowedUtis = <String>[];
  for (final typeGroup in typeGroups) {
    if (typeGroup.allowsAny) return allowAny;
    if (typeGroup.uniformTypeIdentifiers?.isEmpty ?? true) {
      throw ArgumentError(
        'The provided type group $typeGroup should either allow all files, '
        'or have a non-empty "uniformTypeIdentifiers"',
      );
    }
    allowedUtis.addAll(typeGroup.uniformTypeIdentifiers!);
  }
  return allowedUtis;
}

void main() {
  test('invoice type group opens the iOS file picker (has UTIs, never throws)',
      () {
    // The exact call the button makes. On iOS this must NOT throw.
    expect(
      () => _allowedUtiListIos(const [invoiceFileTypes]),
      returnsNormally,
      reason: 'openFile would throw on iOS -> button does nothing',
    );

    final utis = _allowedUtiListIos(const [invoiceFileTypes]);
    expect(utis, isNotEmpty);
    expect(utis, contains('com.adobe.pdf'), reason: 'PDF invoices');
    expect(utis, contains('public.image'), reason: 'photo invoices (jpg/png/webp)');
  });

  test('the invoice group still filters PDFs + images on Android/desktop', () {
    expect(invoiceFileTypes.extensions, containsAll(<String>['pdf', 'jpg', 'png']));
    expect(invoiceFileTypes.mimeTypes, contains('application/pdf'));
    // It must NOT be an "allow anything" group, otherwise the filter is a no-op.
    expect(invoiceFileTypes.allowsAny, isFalse);
  });

  test('a type group WITHOUT uniformTypeIdentifiers throws on iOS (the old bug)',
      () {
    const withoutUtis = XTypeGroup(
      label: 'Factures',
      extensions: ['pdf', 'jpg'],
      mimeTypes: ['application/pdf', 'image/jpeg'],
    );
    expect(() => _allowedUtiListIos(const [withoutUtis]), throwsArgumentError);
  });
}
