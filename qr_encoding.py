from string import ascii_uppercase, digits

# Data Encoding

encoding_modes_data = {
    'numeric': digits,
    'alphanumeric': digits+ascii_uppercase+' $%*+-./:'
}

with open('./data/block_info.txt', 'r') as f:
    block_info = [[int(y) for y in x.split()[1:]] for x in f.readlines()]

def mode_selector(data:str) -> int:
    if all(x in encoding_modes_data['numeric'] for x in data): return 0
    elif all(x in encoding_modes_data['alphanumeric'] for x in data): return 1
    check_bytes = False
    for c in data:
        try:
            c = int(c.encode('shiftjis').hex(), 16)
            if not (0x8140 <= c <= 0x9ffc or 0xe040 <= c <= 0xebbf):
                check_bytes = True
                break
        except:
            check_bytes = True
            break
    if check_bytes:
        for c in data:
            try: c.encode('ISO 8859-1')
            except:
                return -1
        return 2
    return 3

def version_selector(data_size:int, mode:int, ec_level:int) -> int:
    with open('./data/capacities.txt', 'r') as f: capacities = f.read().split()
    version = 1
    while data_size > int(capacities[((version-1)*21+1)+ec_level*5+mode+1]) and version < 41: version += 1
    if version > 40: raise OverflowError('Input data cannot fit in standard V40 QR code.')
    return version

def get_mode_bits(mode:int) -> str:
    return ['0001', '0010', '0100', '1000'][mode]

def get_lenght_bits(lenght:int, mode:int, version:int) -> str:
    if 1 <= version <= 9: bits = [10, 9, 8, 8][mode]
    elif 10 <= version <= 26: bits = [12, 11, 16, 10][mode]
    else: bits = [14, 13, 16, 12][mode]
    return bin(lenght)[2:].zfill(bits)

def get_data_bit_count(ec_level:int, version:int) -> int:
    return block_info[(version-1)*4+ec_level][0]*8

def get_padding(current_lenght:int, ec_level:int, version:int) -> str:
    required_bits = get_data_bit_count(ec_level, version)
    padding = '0'*min(required_bits-current_lenght, 4)
    current_lenght += len(padding)
    padding += '0'*((8-current_lenght%8)%8)
    current_lenght += ((8-current_lenght%8)%8)
    if required_bits > current_lenght:
        for i in range((required_bits-current_lenght)//8):
            if i%2==0: padding += '11101100'
            else: padding += '00010001'
    return padding

def numeric_mode_encoding(data:str) -> list[str]:
    groups = [int(data[i*3:i*3+3]) for i in range(len(data)//3+int(len(data)%3!=0))]
    for i, g in enumerate(groups):
        groups[i] = bin(g)[2:].zfill([4, 7, 10][len(str(g))-1])
    return groups

def alphanumeric_mode_encoding(data: str) -> list[str]:
    groups = [data[i*2:i*2+2] for i in range(len(data)//2+int(len(data)%2!=0))]
    for i, g in enumerate(groups):
        if len(g)==2:
            groups[i] = bin(encoding_modes_data['alphanumeric'].index(g[0])*45 + encoding_modes_data['alphanumeric'].index(g[1]))[2:].zfill(11)
        else:
            groups[i] = bin(encoding_modes_data['alphanumeric'].index(g[0]))[2:].zfill(6)
    return groups

def byte_mode_encoding(data:str) -> list[str]:
    return [bin(c)[2:].zfill(8) for c in data.encode('ISO 8859-1')]

def kanji_mode_encoding(data: str) -> list[str]:
    groups = []
    for c in data:
        c = int(c.encode('shiftjis').hex(), 16)
        if 0x8140 <= c <= 0x9ffc: x = 0x8140
        else: x = 0xc140
        c = hex(c-x)[2:].zfill(4)
        c = bin(int(c[:2], 16)*0xc0 + int(c[2:], 16))[2:].zfill(13)
        groups.append(c)
    return groups

# Block separation

def block_divider(codewords:dict, ec_level:int, version:int) -> list[list[str]]:
    groups = []
    version_info = block_info[(version-1)*4+ec_level]
    b = version_info[2]
    cw = version_info[3]
    [groups.append(codewords[i*cw: (i+1)*cw]) for i in range(b)]
    codewords = codewords[b*cw:]
    if len(version_info) == 6:
        b = version_info[4]
        cw = version_info[5]
        [groups.append(codewords[i*cw: (i+1)*cw]) for i in range(b)]
    return groups

# Galois Field 256

with open('./data/log_antilog.txt', 'r') as f:
    log_antilog = [[int(y) for y in x.split()] for x in f.readlines()]

def to_exp(n:int) -> int:
    assert 0 < n < 256
    return log_antilog[n][3]

def to_number(exp:int) -> int:
    assert 0 <= exp < 256
    return log_antilog[exp][1]

def g_multiply(x:int, y:int):
    res = x+y
    if res >= 256: res %= 255
    return res

# Generator Polynomial

def generate_gen_poly(size:int) -> list[int]:
    if size < 2: raise ValueError('Cannot generate ec polynomial for less than 2 codewords.')
    res = [[0, 1], [0, 0]]
    for n in range(1, size):
        factors = [res, [[0, 1], [n, 0]]]
        factors = [[factors[0][j], factors[1][i]] for i in range(len(factors[1])) for j in range(len(factors[0]))]
        factors = [[to_number(g_multiply(x[0][0], x[1][0])), g_multiply(x[0][1], x[1][1])] for x in factors]
        i = 1
        while len(factors) != n+2:
            for j in range(i+1, len(factors)):
                if factors[i][1] == factors[j][1]:
                    factors[i] = [factors[i][0]^factors[j][0], factors[i][1]]
                    factors.remove(factors[j])
                    break
            else:
                i += 1
        res = [[to_exp(x[0]), x[1]] for x in factors]
    return [x[0] for x in res]

# Error Correction Codewords generator

def generate_ec_codewords(data:list[list[str]], ec_level:int, version:int) -> list[list[str]]:
    n = block_info[(version-1)*4+ec_level][1]
    const_generator = generate_gen_poly(n)
    tmp = data.copy()
    for i, data_block in enumerate(tmp):
        data_block = [int(x, 2) for x in data_block]
        for _ in range(len(data_block)):
            if data_block[0] == 0:
                data_block = data_block[1:]
                continue
            generator = [to_number(g_multiply(x, to_exp(data_block[0]))) for x in const_generator]
            if len(data_block) > len(generator): generator += [0]*(len(data_block)-len(generator))
            else: data_block += [0]*(len(generator)-len(data_block))
            data_block = [x^y for x, y in zip(generator, data_block)][1:]
        if len(data_block) != n: data_block = data_block + [0]*(n-len(data_block))
        tmp[i] = data_block
    return [[bin(y)[2:].zfill(8) for y in x] for x in tmp]

# Message Structuring

def structure_message(data_codewords:list[list[str]], ec_codewords:list[list[str]], version:int) -> str:
    structured_data = ''.join([data_codewords[i][j] for j in range(max([len(x) for x in data_codewords])) for i in range(len(data_codewords)) if len(data_codewords[i]) > j])
    structured_data += ''.join([ec_codewords[i][j] for j in range(len(ec_codewords[0])) for i in range(len(ec_codewords))])
    n = 0
    if 14 <= version <= 20 or 28 <= version <= 34: n = 3
    elif 21 <= version <= 27: n = 4
    elif 2 <= version <= 6: n = 7
    return structured_data + '0'*n

# Encode function

def encode(data:str, ec_level:int) -> dict:
    if not (0 <= ec_level <= 3): raise ValueError('Invalid ec_level set. Should be between 0 and 3 inclusive.')
    mode = mode_selector(data)
    if mode == -1: raise ValueError('Cannot encode UTF-8 characters using standard QR codes. (Please make sure you are not mixing Kanji and ISO 8859-1 characters. Doing so will result in this error.)')
    version = version_selector(len(data), mode, ec_level)
    encoded_data = []
    encoded_data.append(get_mode_bits(mode))
    encoded_data.append(get_lenght_bits(len(data), mode, version))
    match mode:
        case 0: encoded_data.extend(numeric_mode_encoding(data))
        case 1: encoded_data.extend(alphanumeric_mode_encoding(data))
        case 2: encoded_data.extend(byte_mode_encoding(data))
        case 3: encoded_data.extend(kanji_mode_encoding(data))
    encoded_data = ''.join(encoded_data)
    encoded_data += get_padding(len(encoded_data), ec_level, version)
    encoded_data = [encoded_data[i*8:i*8+8] for i in range(len(encoded_data)//8)]
    encoded_data = block_divider(encoded_data, ec_level, version)
    ec_codewords = generate_ec_codewords(encoded_data, ec_level, version)
    structured_message = structure_message(encoded_data, ec_codewords, version)
    return {
        'data': structured_message,
        'version': version,
        'mode': mode,
        'ec_level': ec_level
    }
