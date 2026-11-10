"""Minimal ext2 reader and in-place file replacement, without block allocation."""
import math
import struct


class Ext2:
    def __init__(self, data):
        self.data=data
        if self.u16(1080)!=0xef53:raise ValueError('Not ext2')
        self.bs=1024<<self.u32(1048)
        self.blocks=self.u32(1028)
        self.ipg=self.u32(1064)
        self.inode_size=self.u16(1112) or 128
        self.gdt=(self.u32(1044)+1)*self.bs
        if self.bs not in (1024,2048,4096) or self.u32(1120)&~2:
            raise ValueError('Unsupported filesystem features')
        if self.blocks*self.bs>len(data) or not self.ipg or self.inode_size<128:
            raise ValueError('Invalid filesystem dimensions')

    def u16(self,at):return struct.unpack_from('<H',self.data,at)[0]
    def u32(self,at):return struct.unpack_from('<I',self.data,at)[0]
    def inode(self,number):
        if not 0<number<=self.u32(1024):raise ValueError('Invalid inode')
        group,index=divmod(number-1,self.ipg)
        return self.u32(self.gdt+group*32+8)*self.bs+index*self.inode_size

    def block(self,inode,index):
        p=self.bs//4
        if index<12:value=self.u32(inode+40+index*4)
        else:
            index-=12
            for level in range(1,4):
                if index<p**level:
                    value=self.u32(inode+40+(11+level)*4)
                    for depth in range(level-1,-1,-1):
                        digit,index=divmod(index,p**depth)
                        if not 0<value<self.blocks:raise ValueError('Sparse or invalid indirect block')
                        value=self.u32(value*self.bs+digit*4)
                    break
                index-=p**level
            else:raise ValueError('File too large')
        if not 0<value<self.blocks:raise ValueError('Sparse or invalid data block')
        return value

    def contents(self,inode):
        size=self.u32(inode+4)
        if self.u16(inode)&0xf000==0x8000 and self.u32(inode+108):raise ValueError('Large file unsupported')
        return b''.join(self.data[self.block(inode,i)*self.bs:(self.block(inode,i)+1)*self.bs]
                        for i in range(math.ceil(size/self.bs)))[:size]

    def find(self,path):
        number=2
        for part in path.strip('/').split('/'):
            inode=self.inode(number)
            if self.u16(inode)&0xf000!=0x4000:raise ValueError('Non-directory path component')
            entries=self.contents(inode);pos=0;found=None
            while pos<len(entries):
                child,length,name_size,kind=struct.unpack_from('<IHBB',entries,pos)
                if length<8 or length%4 or pos+length>len(entries) or name_size>length-8:
                    raise ValueError('Invalid directory record')
                if child and entries[pos+8:pos+8+name_size]==part.encode():
                    if found is not None:raise ValueError('Duplicate directory entry')
                    found=child
                pos+=length
            if found is None:raise ValueError('File not found: '+path)
            number=found
        return self.inode(number)

    def replace(self,path,expected,replacement):
        inode=self.find(path)
        if self.u16(inode)&0xf000!=0x8000 or self.contents(inode)!=expected:
            raise ValueError('Wrong file preimage: '+path)
        if math.ceil(len(expected)/self.bs)!=math.ceil(len(replacement)/self.bs):
            raise ValueError('Replacement would allocate or free blocks')
        for i in range(math.ceil(len(replacement)/self.bs)):
            chunk=replacement[i*self.bs:(i+1)*self.bs]
            at=self.block(inode,i)*self.bs
            self.data[at:at+len(chunk)]=chunk
        struct.pack_into('<I',self.data,inode+4,len(replacement))
        if self.contents(inode)!=replacement:raise ValueError('File verification failed')
        return inode
