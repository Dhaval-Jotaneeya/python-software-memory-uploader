from PyQt6.QtWidgets import QLayout
from PyQt6.QtCore import QRect, QSize, QPoint, Qt

class MasonryLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=6, columns=6):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []
        self.columns = columns

    def addItem(self, item):
        self.itemList.append(item)

    def count(self):
        return len(self.itemList)

    def itemAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.itemList):
            return self.itemList.pop(index)
        return None

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.doLayout(rect)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self.itemList:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def doLayout(self, rect):
        if not self.itemList:
            return
        spacing = self.spacing()
        columns = self.columns
        col_width = (rect.width() - (columns - 1) * spacing) // columns
        y_offsets = [rect.y()] * columns
        for item in self.itemList:
            w = col_width
            h = item.sizeHint().height()
            col = y_offsets.index(min(y_offsets))
            x = rect.x() + col * (col_width + spacing)
            y = y_offsets[col]
            item.widget().setFixedWidth(col_width)
            item.setGeometry(QRect(QPoint(x, y), QSize(col_width, h)))
            y_offsets[col] += h + spacing

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))