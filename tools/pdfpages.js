// Rasterise every page of a PDF to PNG with PDFKit through JavaScript for Automation.
// No compiler and no poppler needed.
// Usage: osascript -l JavaScript tools/pdfpages.js IN.pdf OUT_DIR [scale=2]
ObjC.import('AppKit');
ObjC.import('PDFKit');
function run(argv) {
  var scale = argv.length > 2 ? parseFloat(argv[2]) : 2;
  var doc = $.PDFDocument.alloc.initWithURL($.NSURL.fileURLWithPath(argv[0]));
  $.NSFileManager.defaultManager.createDirectoryAtPathWithIntermediateDirectoriesAttributesError(argv[1], true, $(), $());
  var n = doc.pageCount;
  for (var i = 0; i < n; i++) {
    var page = doc.pageAtIndex(i);
    var box = page.boundsForBox($.kPDFDisplayBoxMediaBox);
    var img = page.thumbnailOfSizeForBox($.NSMakeSize(box.size.width * scale, box.size.height * scale), $.kPDFDisplayBoxMediaBox);
    var rep = $.NSBitmapImageRep.imageRepWithData(img.TIFFRepresentation);
    var png = rep.representationUsingTypeProperties($.NSBitmapImageFileTypePNG, $());
    var name = argv[1] + '/p' + (i < 9 ? '0' : '') + (i + 1) + '.png';
    png.writeToFileAtomically(name, true);
  }
  return n + ' pages -> ' + argv[1];
}
