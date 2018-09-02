import views

if __name__ == '__main__':
    vs = views.ViewSettings(
        ['base', 'Singles'],
        views.get_output_line('Artist', 'Album', 'Title'),
        views.artist_sorter)

    views.singles_view(vs)
