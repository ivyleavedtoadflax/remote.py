def get_column_widths(columns):
    """Get the width of each column in a list of lists.
    """
    widths = []

    for column in columns:
        widths.append(max([len(str(i)) for i in column]))

    return widths
