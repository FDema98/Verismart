extern void __VERIFIER_error() __attribute__ ((__noreturn__));

#include <pthread.h>
#include <assert.h>

pthread_mutex_t  m;
int data = 0;

void *thread1(void *arg)
{
  pthread_mutex_lock(&m);
  data++;
  pthread_mutex_unlock(&m);
}


void *thread2(void *arg)
{
  pthread_mutex_lock(&m);
  data+=2;
  pthread_mutex_unlock(&m);
}

int foo(int x){
   return x+1;
}

void *thread3(void *arg)
{
  int x;

  pthread_mutex_lock(&m);
  if (data >= 3){
    ERROR: __VERIFIER_error();
    ;
  }
  pthread_mutex_unlock(&m);
 
  x = 5 + foo(x);
}


int main()
{
  pthread_mutex_init(&m, 0);

  pthread_t t1, t2, t3;

  pthread_create(&t1, 0, thread1, 0);
  pthread_create(&t2, 0, thread2, 0);
  pthread_create(&t3, 0, thread3, 0);

  pthread_join(t1, 0);
  pthread_join(t2, 0);
  pthread_join(t3, 0);

  return 0;
}
