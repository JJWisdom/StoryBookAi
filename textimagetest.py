from PIL import Image
im = Image.open("Roadie1.png")
print(im.format, im.size, im.mode)
im.show()