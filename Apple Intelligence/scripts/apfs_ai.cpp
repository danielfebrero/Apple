// Offline APFS reader, derived from /workspace/opt/build/dscextract.cpp.
// Keeps its known-good checkpoint (req_xid=1000000) and one-process-per-file model.
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <string>
#include <vector>
#include <iostream>
#include <ApfsLib/Device.h>
#include <ApfsLib/ApfsContainer.h>
#include <ApfsLib/ApfsVolume.h>
#include <ApfsLib/ApfsDir.h>
#include <ApfsLib/Decmpfs.h>
#include <ApfsLib/GptPartitionMap.h>
#include <ApfsLib/DiskStruct.h>
static const uint64_t REQ_XID=1000000;
static std::string json(const std::string &s) {
 std::string o="\"";
 for(unsigned char c:s) { if(c=='"'||c=='\\'){o+='\\';o+=c;} else if(c<32){char b[7];snprintf(b,sizeof(b),"\\u%04x",c);o+=b;}else o+=c; } return o+'"';
}
static void walk(ApfsDir &d,uint64_t inode,const std::string &p) {
 std::vector<ApfsDir::DirRec> ls;
 if(!d.ListDirectory(ls,inode)){std::cerr<<"ListDirectory failed "<<p<<" inode="<<inode<<"\n";return;}
 for(const auto &r:ls){
  std::string q=p+"/"+r.name;unsigned t=r.flags&DREC_TYPE_MASK;
  ApfsDir::Inode i;bool got=d.GetInode(i,r.file_id);
  uint64_t size=got?((i.optional_present_flags&ApfsDir::Inode::INO_HAS_DSTREAM)?i.ds_size:i.uncompressed_size):0;
  std::cout<<"{\"path\":"<<json(q)<<",\"kind\":"<<t<<",\"inode\":"<<r.file_id<<",\"private_id\":"<<(got?i.private_id:0)<<",\"size\":"<<size<<",\"uncompressed_size\":"<<(got?i.uncompressed_size:0)<<",\"bsd_flags\":"<<(got?i.bsd_flags:0)<<",\"inode_ok\":"<<(got?"true":"false")<<"}\n";
  if(t==DT_DIR)walk(d,r.file_id,q);
 }
}
int main(int argc,char **argv){
 if(argc<3){std::cerr<<"Usage: apfs_ai inventory <dmg> | one <dmg> <inode> <private_id> <size> <out>\n";return 2;}
 Device *dev=Device::OpenDevice(argv[2]);if(!dev)return 1;
 uint64_t off=0,sz=dev->GetSize();GptPartitionMap gpt;
 if(gpt.LoadAndVerify(*dev)){int pid=gpt.FindFirstAPFSPartition();if(pid!=-1)gpt.GetPartitionOffsetAndSize(pid,off,sz);}
 ApfsContainer *c=new ApfsContainer(dev,off,sz);if(!c->Init(REQ_XID))return 1;
 ApfsVolume *v=c->GetVolume(0);if(!v)return 1;
 std::cerr<<"volume="<<v->name()<<" sealed="<<v->isSealed()<<" req_xid="<<REQ_XID<<"\n";ApfsDir d(*v);
 if(std::string(argv[1])=="inventory"){walk(d,ROOT_DIR_INO_NUM,"");return 0;}
 if(std::string(argv[1])!="one"||argc!=7)return 2;
 uint64_t inode=strtoull(argv[3],0,0),priv=strtoull(argv[4],0,0),size=strtoull(argv[5],0,0);
 ApfsDir::Inode ino;if(!d.GetInode(ino,inode)){std::cerr<<"GetInode failed\n";return 1;}
 FILE *out=fopen(argv[6],"wb");if(!out){std::cerr<<"Output open failed\n";return 1;}
 uint64_t written=0;bool ok=true;
 if(ino.bsd_flags&0x20){std::vector<uint8_t> attr,bytes;ok=d.GetAttribute(attr,inode,"com.apple.decmpfs")&&DecompressFile(d,inode,bytes,attr);if(ok){written=fwrite(bytes.data(),1,bytes.size(),out);ok=written==bytes.size();}}
 else{std::vector<uint8_t> bytes(16*1024*1024);while(written<size){size_t n=std::min<uint64_t>(bytes.size(),size-written);if(!d.ReadFile(bytes.data(),priv,written,n)){ok=false;break;}size_t nw=fwrite(bytes.data(),1,n,out);written+=nw;if(nw!=n){ok=false;break;}}}
 fclose(out);std::cout<<written<<"\n";return ok?0:1;
}
