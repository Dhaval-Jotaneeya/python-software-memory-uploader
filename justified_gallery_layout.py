from PyQt6.QtWidgets import QLayout
from PyQt6.QtCore import QRect, QSize, QPoint, Qt

class JustifiedGalleryLayout(QLayout):
    def __init__(self, parent=None, margin=0, spacing=6, row_height=120):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self.itemList = []
        self.row_height = row_height

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
        x = rect.x()
        y = rect.y()
        row = []
        row_width = 0
        max_width = rect.width()
        total_height = 0
        for item in self.itemList:
            widget = item.widget()
            pixmap = widget.pixmap() if hasattr(widget, 'pixmap') else None
            if pixmap is not None and not pixmap.isNull():
                aspect = pixmap.width() / pixmap.height()
            else:
                aspect = 1.0
            width = int(self.row_height * aspect)
            row.append((item, width, self.row_height))
            row_width += width + spacing
            # If row is full, layout the row
            if row_width - spacing > max_width and len(row) > 1:
                # Scale widths to fill the row
                total_width = sum(w for _, w, _ in row)
                scale = (max_width - spacing * (len(row) - 1)) / total_width
                cur_x = x
                for i, (item, w, h) in enumerate(row):
                    new_w = int(w * scale)
                    item.setGeometry(QRect(QPoint(cur_x, y), QSize(new_w, self.row_height)))
                    cur_x += new_w + spacing
                y += self.row_height + spacing
                total_height = y
                row = []
                row_width = 0
        # Layout any remaining items in the last row
        if row:
            cur_x = x
            for i, (item, w, h) in enumerate(row):
                item.setGeometry(QRect(QPoint(cur_x, y), QSize(w, self.row_height)))
                cur_x += w + spacing
            y += self.row_height + spacing
            total_height = y
        # Set the parent widget's minimum height to total_height
        if self.parentWidget() is not None:
            self.parentWidget().setMinimumHeight(total_height)

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def invalidate(self):
        self.update() 