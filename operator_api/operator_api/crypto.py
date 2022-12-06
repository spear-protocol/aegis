import bitcoin
import random

from eth_utils import keccak, decode_hex, int_to_big_endian, big_endian_to_int, encode_hex, remove_0x_prefix, is_hex
from ecdsa import SigningKey, SECP256k1


def uint512(x):
    return zfill(unsigned_int_to_bytes(int(x)), 64)


def uint256(x):
    return zfill(unsigned_int_to_bytes(int(x)))


def uint32(x):
    return zfill(unsigned_int_to_bytes(int(x)), 4)


def uint64(x):
    return zfill(unsigned_int_to_bytes(int(x)), 8)


def int256(x):
    return zfill(signed_int_to_bytes(int(x)))


def address(s):
    return zfill(decode_hex(s), 20) if is_hex(s) else zfill(s, 20)


def hex_address(s):
    return remove_0x_prefix(hex_value(address(s)))[-40:] if is_hex(s) else hex_address(hex_value(s))


def zfill(x, p=32):
    return (p - len(x))*b'\x00' + x


def unsigned_int_to_bytes(x):
    return int_to_big_endian(x)


def signed_int_to_bytes(x):
    # pyethereum int to bytes does not handle negative numbers
    assert -(1 << 255) <= x < (1 << 255)
    return int_to_big_endian((1 << 256) + x if x < 0 else x)


def hash_message(m):
    return keccak(b'\x19Ethereum Signed Message:\n32' + m)


def has_lqd_message(m):
    return hash_message(keccak(b'\x19Liquidity.Network Authorization:\n32' + m))


def sign_message(m, k):
    h = has_lqd_message(m)
    return sign(h, k)


def sign(h, priv):
    assert len(h) == 32
    v, r, s = bitcoin.ecdsa_raw_sign(h, priv)
    return v, r, s


def verify_message_signature(addr, m, v_r_s):
    h = has_lqd_message(m)
    return verify_signature(addr, h, v_r_s)


def verify_signature(addr, h, v_r_s):
    pub = bitcoin.ecdsa_raw_recover(h, v_r_s)
    pub = bitcoin.encode_pubkey(pub, 'bin')
    addr_ = keccak(pub[1:])[12:]
    return addr_.lower() == addr.lower()


def hex_value(bytes_value):
    return remove_0x_prefix(encode_hex(bytes_value))


def encode_decimal(dec):
    return int(dec).to_bytes(32, byteorder='big')


def parse_web3_sig(rsv):
    return encode_signature((int(rsv[128:130]),
                             big_endian_to_int(decode_hex(rsv[0:64])),
                             big_endian_to_int(decode_hex(rsv[64:128]))))


def encode_signature(vrs):
    return hex_value(join_signature_to_rsv(*vrs))


def decode_signature(encoded_rsv):
    return decompose_sig_to_vrs(decode_hex(encoded_rsv))


def join_signature_to_rsv(v, r, s):
    return uint256(r) + uint256(s) + int_to_big_endian(v)


def decompose_sig_to_vrs(rsv):
    return big_endian_to_int(rsv[64:65]),\
        big_endian_to_int(rsv[0:32]),\
        big_endian_to_int(rsv[32:64])


def hash_array_pad(arr):
    return keccak(b''.join([zfill(x) for x in arr]))


def hash_array(arr):
    return keccak(b''.join(arr))


def generate_wallet():
    private_key = SigningKey.generate(curve=SECP256k1)
    public_key = private_key.get_verifying_key().to_string()
    wallet_address = keccak(public_key).hex()[24:]

    return private_key, public_key, wallet_address


def random_wei():
    return int(random.random()*1e18 + 2020)


def same_hex_value(a, b):
    return remove_0x_prefix(a).lower() == remove_0x_prefix(b).lower()
