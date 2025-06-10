scroll_script = """
    let totalHeight = 0;
    const distance = 200;
    const delay = 100;
    const scroll = () => {
        window.scrollBy(0, distance);
        totalHeight += distance;

        if (totalHeight < document.body.scrollHeight) {
            setTimeout(scroll, delay);
        }
    };
    scroll();
"""