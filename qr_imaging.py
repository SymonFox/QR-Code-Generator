from PIL import Image, ImageOps
from qr_encoding import encode
import sys

with open('./data/pattern_locations.txt') as f:
    pattern_locations = [[int(y) for y in x.split()] for x in f.readlines()]

# Finder pattern
finder_pattern = []
finder_pattern.append([1, 1, 1, 1, 1, 1, 1])
finder_pattern.append([1, 0, 0, 0, 0, 0, 1])
finder_pattern.append([1, 0, 1, 1, 1, 0, 1])
finder_pattern.append([1, 0, 1, 1, 1, 0, 1])
finder_pattern.append([1, 0, 1, 1, 1, 0, 1])
finder_pattern.append([1, 0, 0, 0, 0, 0, 1])
finder_pattern.append([1, 1, 1, 1, 1, 1, 1])


# Alignment pattern
alignment_pattern = []
alignment_pattern.append([1, 1, 1, 1, 1])
alignment_pattern.append([1, 0, 0, 0, 1])
alignment_pattern.append([1, 0, 1, 0, 1])
alignment_pattern.append([1, 0, 0, 0, 1])
alignment_pattern.append([1, 1, 1, 1, 1])

def generate_format_string(ec_level:int, mask_pattern:int) -> str:
    generator = '10100110111'
    ec_bits = ['01', '00', '11', '10'][ec_level]
    mask_pattern_bits = bin(mask_pattern)[2:].zfill(3)
    format_bits = int(ec_bits+mask_pattern_bits+'0'*10, 2)
    while format_bits.bit_length() >= 11: format_bits = format_bits^int(generator.ljust(format_bits.bit_length(), '0'), 2)
    return bin(int('101010000010010', 2)^int(ec_bits+mask_pattern_bits+bin(format_bits)[2:].zfill(10), 2))[2:].zfill(15)

def generate_version_information(version:int) -> str:
    generator = '1111100100101'
    version_bits = int(bin(version)[2:].zfill(6).ljust(18, '0'), 2)
    while version_bits.bit_length() > 12: version_bits = version_bits^int(generator.ljust(version_bits.bit_length(), '0'), 2)
    return bin(version)[2:].zfill(6)+bin(version_bits)[2:].zfill(12)

def get_alignment_coords(version:int) -> list[tuple[int]]:
    if version <= 1: return []
    pattern_coords = pattern_locations[version-2]
    alignment_coords = []
    for i in range(len(pattern_coords)):
            for j in range(len(pattern_coords)):
                current_coords = (pattern_coords[i], pattern_coords[j])
                if not ((current_coords[0] == pattern_coords[0] and current_coords[1] == pattern_coords[0]) or 
                        (current_coords[0] == pattern_coords[0] and current_coords[1] == pattern_coords[-1]) or
                        (current_coords[0] == pattern_coords[-1] and current_coords[1] == pattern_coords[0])):
                    alignment_coords.append(current_coords)
    return alignment_coords        

def paste_to_matrix(matrix:list[list[int]], value:int, start:tuple[int, int], width:int, height:int) -> None:
    for h in range(start[1], start[1]+height):
        for w in range(start[0], start[0]+width):
            matrix[h][w] = value

def paste_matrix_to_matrix(matrix:list[list[int]], to_paste:list[list[int]], start:tuple[int, int]) -> None:
    for y in range(len(to_paste)):
        for x in range(len(to_paste[0])):
            matrix[y+start[1]][x+start[0]] = to_paste[y][x]


def align_data(data:dict) -> list[int]:
    # Matrix generation and data blocking
    data_matrix = []
    alignment_coords = get_alignment_coords(data['version'])
    [data_matrix.append([0]*((data['version']-1)*4+21)) for _ in range((data['version']-1)*4+21)]
    paste_to_matrix(data_matrix, 2, (0, 0), 9, 9)
    paste_to_matrix(data_matrix, 2, ((data['version']-1)*4+13, 0), 8, 9)
    paste_to_matrix(data_matrix, 2, (0, (data['version']-1)*4+13), 9, 8)
    for x in alignment_coords:
        paste_to_matrix(data_matrix, 2, (x[0]-2, x[1]-2), 5, 5)
    if data['version'] >= 7:
        paste_to_matrix(data_matrix, 2, ((data['version']-1)*4+10, 0), 3, 6)
        paste_to_matrix(data_matrix, 2, (0, (data['version']-1)*4+10), 6, 3)
    paste_to_matrix(data_matrix, 2, (0, 6), len(data_matrix), 1)
    paste_to_matrix(data_matrix, 3, (6, 0), 1, len(data_matrix))
    
    # Data placement
    x = -1
    y = -1
    direction = True
    cicle = True
    i = 0
    while i < len(data['data']):
        assert -len(data_matrix[0])-1 < x < 0
        if y == -len(data_matrix)-1 or y == 0:
            if direction: y += 1
            else: y -= 1
            x -= 2
            direction = not direction
        if data_matrix[y][x] != 2:
            if data_matrix[y][x] == 3: x -= 1
            else:
                data_matrix[y][x] = int(data['data'][i])
                i += 1
        if cicle:
            x -= 1
        else:
            x += 1
            if direction: y -= 1
            else: y += 1
        cicle = not cicle
    
    # Clean up
    for x in data_matrix: 
        for i in range(len(x)):
            if x[i] > 1: x[i] = 0

    # Masking
    const_matrix = data_matrix
    matrices = []
    for mask in range(8):
        data_matrix = [x.copy() for x in const_matrix]
        match mask:
            case 0:
                for row in range(len(data_matrix)):
                    for column in range(len(data_matrix[0])):
                        if (row+column)%2==0: data_matrix[row][column] ^= 1
            case 1:
                for row in range(len(data_matrix)):
                    for column in range(len(data_matrix[0])):
                        if (row)%2==0: data_matrix[row][column] ^= 1
            case 2:
                for row in range(len(data_matrix)):
                    for column in range(len(data_matrix[0])):
                        if (column)%3==0: data_matrix[row][column] ^= 1
            case 3:
                for row in range(len(data_matrix)):
                    for column in range(len(data_matrix[0])):
                        if (row+column)%3==0: data_matrix[row][column] ^= 1
            case 4:
                for row in range(len(data_matrix)):
                    for column in range(len(data_matrix[0])):
                        if (row//2+column//3)%2==0: data_matrix[row][column] ^= 1
            case 5:
                for row in range(len(data_matrix)):
                    for column in range(len(data_matrix[0])):
                        if ((row*column)%2)+((row*column)%3)==0: data_matrix[row][column] ^= 1
            case 6:
                for row in range(len(data_matrix)):
                    for column in range(len(data_matrix[0])):
                        if (((row*column)%2)+((row*column)%3))%2==0: data_matrix[row][column] ^= 1
            case 7:
                for row in range(len(data_matrix)):
                    for column in range(len(data_matrix[0])):
                        if (((row+column)%2)+((row*column)%3))%2==0: data_matrix[row][column] ^= 1

        # Placing format string
        format_string = generate_format_string(data['ec_level'], mask)
        paste_matrix_to_matrix(data_matrix, [[int(x) for x in format_string[:6]]], (0, 8))
        paste_matrix_to_matrix(data_matrix, [[int(x) for x in format_string[7:]]], ((data['version']-1)*4+13, 8))
        data_matrix[8][7] = int(format_string[6])
        paste_matrix_to_matrix(data_matrix, [[int(format_string[i])] for i in range(6, -1, -1)], (8, (data['version']-1)*4+14))
        paste_matrix_to_matrix(data_matrix, [[int(format_string[i])] for i in range(14, 8, -1)], (8, 0))
        data_matrix[7][8] = int(format_string[8])
        data_matrix[8][8] = int(format_string[7])

        # Placing version information
        if data['version'] >= 7:
            version_info = [x for x in reversed(generate_version_information(data['version']))]
            bl_version_info = []
            for j in range(3):
                tmp = []
                for i in range(j, len(version_info), 3): tmp.append(int(version_info[i]))
                bl_version_info.append(tmp)
            paste_matrix_to_matrix(data_matrix, bl_version_info, (0, (data['version']-1)*4+10))
            tr_version_info = []
            for j in range(0, len(version_info), 3):
                tmp = []
                for i in range(3): tmp.append(int(version_info[j+i]))
                tr_version_info.append(tmp)
            paste_matrix_to_matrix(data_matrix, tr_version_info, ((data['version']-1)*4+10, 0))

        # Placing finder and alignment patterns
        paste_matrix_to_matrix(data_matrix, [[int(not x%2) for x in range((data['version']-1)*4+21)]], (0, 6))
        paste_matrix_to_matrix(data_matrix, [[int(not x%2)] for x in range((data['version']-1)*4+21)], (6, 0))
        paste_matrix_to_matrix(data_matrix, finder_pattern, (0, 0))
        paste_matrix_to_matrix(data_matrix, finder_pattern, ((data['version']-1)*4+14, 0))
        paste_matrix_to_matrix(data_matrix, finder_pattern, (0, (data['version']-1)*4+14))
        v_line = [[0] for _ in range(8)]
        h_line = [[0]*8]
        paste_matrix_to_matrix(data_matrix, v_line, (7, 0))
        paste_matrix_to_matrix(data_matrix, h_line, (0, 7))
        paste_matrix_to_matrix(data_matrix, v_line, ((data['version']-1)*4+13, 0))
        paste_matrix_to_matrix(data_matrix, h_line, ((data['version']-1)*4+13, 7))
        paste_matrix_to_matrix(data_matrix, v_line, (7, (data['version']-1)*4+13))
        paste_matrix_to_matrix(data_matrix, h_line, (0, (data['version']-1)*4+13))
        for x in alignment_coords: paste_matrix_to_matrix(data_matrix, alignment_pattern, (x[0]-2, x[1]-2))
        data_matrix[(4*data['version'])+9][8] = 1
        matrices.append(data_matrix)
    
    penalties = []
    for matrix in matrices:
        penalty = 0

        # Evaluate penalty 1
        for row in matrix:
            count = 0
            for module in row:
                if module == 1: count += 1
                else: count = 0
                if count == 5: penalty += 3
                elif count > 5: penalty += 1
        for x in range(len(matrix[0])):
            count = 0
            for y in range(len(matrix)):
                if matrix[y][x] == 1: count += 1
                else: count = 0
                if count == 5: penalty += 3
                elif count > 5: penalty += 1
        
        # Evaluate penalty 2
        for y in range(len(matrix)-1):
            for x in range(len(matrix[0])-1):
                current_color = matrix[x][y]
                if matrix[y][x+1] == current_color and matrix[y+1][x] == current_color and matrix[y+1][x+1] == current_color:
                    penalty += 3

        # Evaluate penalty 3
        main_pattern = [1, 0, 1, 1, 1, 0, 1]
        padding = [0]*4
        for y in range(len(matrix)):
            for x in range(len(matrix[0])-10):
                if matrix[y][x: x+11] == main_pattern+padding or matrix[y][x: x+11] == padding+main_pattern:
                    penalty += 40
        inv_coord_matrix:list[list] = []
        for x in range(len(matrix[0])):
            inv_coord_matrix.append([])
            for y in range(len(matrix)):
                inv_coord_matrix[x].append(matrix[y][x])
        for y in range(len(inv_coord_matrix)):
            for x in range(len(inv_coord_matrix[0])-10):
                if inv_coord_matrix[y][x: x+11] == main_pattern+padding or inv_coord_matrix[y][x: x+11] == padding+main_pattern:
                    penalty += 40

        #Evaluate penalty 4
        total_modules = len(matrix)**2
        flat_matrix = []
        for x in matrix: flat_matrix.extend(x)
        dark_modules = sum(flat_matrix)
        dark_percentage = int(dark_modules/total_modules*100)
        prev_percentage = dark_percentage - dark_percentage%5
        next_percentage = prev_percentage+5
        penalty += min(abs(prev_percentage-50)//5, abs(next_percentage-50)//5)*10

        penalties.append(penalty)

    # Flatten
    flat_matrix = []
    for x in matrices[penalties.index(min(penalties))]: flat_matrix.extend(x)
    return flat_matrix

def encoded_to_image(data:dict) -> Image:
    V = data['version']
    im = Image.new('1', ((V-1)*4+21, (V-1)*4+21), 0)
    im.putdata(align_data(data))
    im = im.convert('L')
    im = ImageOps.invert(im)
    frame = Image.new('L', ((V-1)*4+29, (V-1)*4+29), 255)
    frame.paste(im, (4, 4))
    frame = frame.resize((frame.size[0]*10, frame.size[1]*10), resample=Image.BOX)
    return frame

if len(sys.argv) != 3 and len(sys.argv) != 1 : raise ValueError(f'Zero or Two positional arguments are required (data, ec_level), {len(sys.argv)-1} were found instead')

if len(sys.argv) != 1:
    data = sys.argv[1]
    ec_level = int(sys.argv[2])
else:
    import random
    data = ''.join(random.choices(list('1234567890'), k=7000))
    ec_level = 0

enc = encode(data, ec_level)
qr = encoded_to_image(enc)
qr.save('output.png')
qr.show()
