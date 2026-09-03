// Aurelex boundary — shim for the upstream-generated `ui_fulltextsearch.h`.
//
// Upstream builds this header from `src/ui/fulltextsearch.ui` via Qt uic.
// The carve does not build the FTS dialog, but `common/globalregex.cc`
// includes `fulltextsearch.hh` (for the FTS::* enums), which in turn
// includes `ui_fulltextsearch.h`. This minimal declaration satisfies that
// include without pulling in the Qt Widgets UI tree.
#pragma once

#include <QDialog>
#include <QWidget>

namespace Ui {

class FullTextSearchDialog
{
public:
  void setupUi( QWidget * )
  {
  }
  void retranslateUi( QWidget * )
  {
  }
};

} // namespace Ui