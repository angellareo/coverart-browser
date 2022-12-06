# Rhythmbox coverart browser development notes

## Columns in song list view

In file coverart_entryview:
```
self.col_map = OrderedDict([
            ('track-number', RB.EntryViewColumn.TRACK_NUMBER),
            ('title', RB.EntryViewColumn.TITLE),
            ('artist', RB.EntryViewColumn.ARTIST),
            ('album', RB.EntryViewColumn.ALBUM),
            ('year', RB.EntryViewColumn.YEAR),
            ('genre', RB.EntryViewColumn.GENRE),
            ('rating', RB.EntryViewColumn.RATING),
            ('duration', RB.EntryViewColumn.DURATION)
        ])
```
